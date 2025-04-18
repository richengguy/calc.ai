import shutil
from dataclasses import dataclass
from pathlib import Path

import click
import jinja2
import matplotlib.pyplot as plt
import numpy as np
import torch
from rich import box
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

from ._console import clear_screen, console, print
from .model import CalculatorLanguageModel
from .training import (
    ExpressionGenerator,
    ModelTrainer,
    SampleData,
    SampleWriter,
    ScriptBuilder,
    TrainingIteration,
    TrainingSummary,
    from_jsonlines,
)


def _create_report(path: Path, model_name: str, summary: TrainingSummary) -> None:
    env = jinja2.Environment(loader=jinja2.PackageLoader(__package__))

    path.mkdir(parents=True)

    readme_path = path / "README.md"
    training_loss_png = path / "training-loss.png"
    validation_loss_png = path / "validation-loss.png"
    validation_accuracy_png = path / "test-accuracy.png"

    # Create the training loss figure.
    training_loss: list[float] = []
    for epoch_loss in summary.training_loss:
        training_loss.extend(epoch_loss)

    smoothed_loss = np.pad(training_loss, [25, 24], mode="edge")
    smoothed_loss = np.convolve(smoothed_loss, np.ones(50) / 50, mode="valid")

    fig, ax = plt.subplots()
    ax.plot(training_loss, label="Original")
    ax.plot(smoothed_loss, label="Smoothed")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Loss")
    ax.legend()
    fig.savefig(training_loss_png)

    # Create the validation loss figure.
    fig, ax = plt.subplots()
    ax.plot(summary.validation_loss)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    fig.savefig(validation_loss_png)

    # Create the validation accuracy figure.
    fig, ax = plt.subplots()
    ax.plot(
        [100 * accuracy for accuracy, _ in summary.validation_accuracy],
        label="Accuracy",
    )
    ax.plot(
        [100 * invalid for _, invalid in summary.validation_accuracy], label="Invalid"
    )
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Percentage (%)")
    ax.legend()
    fig.savefig(validation_accuracy_png)

    # Generate the report README.
    template = env.get_template("report.md.j2")
    final_accuracy, final_invalids = summary.validation_accuracy[-1]
    readme = template.render(
        model_name=model_name,
        epochs=summary.epochs,
        accuracy=final_accuracy,
        invalid=final_invalids,
        images={
            "training_loss": training_loss_png,
            "validation_loss": validation_loss_png,
            "validation_accuracy": validation_accuracy_png,
        },
    )
    with readme_path.open("wt") as f:
        f.write(readme)


def _update_training_display(progress: Progress, iter: TrainingIteration) -> Table:
    predicted_result = "N/A" if iter.predicted_result is None else iter.predicted_result

    model = Table(expand=True, show_header=False, box=box.MINIMAL)
    model.add_row(f"Ground Truth » {iter.expected}")
    model.add_row(f"CLM Response » {iter.actual}")
    model.add_row(f"Est. Result  » {predicted_result}")
    model.add_section()
    model.add_row(f"Loss         » {iter.loss}")

    epoch_loss = "N/A" if iter.test_loss is None else iter.test_loss
    epoch_accuracy = (
        "N/A" if iter.test_accuracy is None else f"{iter.test_accuracy[0] * 100}%"
    )
    epoch_invalid = (
        "N/A" if iter.test_accuracy is None else f"{iter.test_accuracy[1] * 100}%"
    )

    overall = Table.grid()
    overall.add_row(progress)
    overall.add_row("")
    overall.add_row(f"Test Loss :arrow_forward: {epoch_loss}")
    overall.add_row(f" Accuracy :arrow_forward: {epoch_accuracy}")
    overall.add_row(f"  Invalid :arrow_forward: {epoch_invalid}")

    table = Table.grid(expand=True)
    table.add_column(width=40, min_width=40, max_width=40)
    table.add_column(justify="left", width=80)
    table.add_row(
        Panel(overall, title="Training Progress", width=40, padding=(1, 0)),
        Panel(
            model,
            box=box.SQUARE,
            title=f"Epoch {iter.epoch} :: Iteration {iter.iteration}",
        ),
    )

    return table


@dataclass(frozen=True)
class CliContext:
    models: Path


@click.group()
@click.pass_context
@click.option(
    "--models",
    type=click.Path(dir_okay=True, path_type=Path),
    default=Path("./models"),
    help="Directory where models are stored.",
)
def main(ctx: click.Context, models: Path) -> None:
    """Transformer-based Calculator"""
    models.mkdir(parents=True, exist_ok=True)
    ctx.obj = CliContext(models)


@main.command()
@click.option(
    "-n",
    "--samples",
    metavar="N",
    default=1000,
    help="Number of training samples to generate.",
)
@click.option(
    "-d",
    "--depth",
    metavar="N",
    default=3,
    help="Depth, or complexity, of the generated expressions.",
)
@click.option(
    "-m",
    "--max",
    "max_value",
    metavar="N",
    default=25,
    help="Maximum integer value in any generated expression.",
)
@click.option(
    "-v",
    "--variable",
    "vars",
    multiple=True,
    help="Specify a possible variable name.  Can be repeated.",
)
@click.option(
    "-s",
    "--generate-solutions",
    is_flag=True,
    help="Also generate the solution steps for each sample.",
)
@click.argument("output", type=click.Path(path_type=Path))
def generate_data(
    samples: int,
    depth: int,
    max_value: int,
    vars: list[str],
    generate_solutions: bool,
    output: Path,
) -> None:
    """Generate training data for the language model.

    The training data is saved into OUTPUT as a JSONL file, where each line is a
    single JSON object.
    """
    with SampleWriter(output) as writer:
        generator = ExpressionGenerator(max_value)
        builder = ScriptBuilder(generator, expr_depth=depth)
        builder.set_variables(vars)
        builder.show_steps(generate_solutions)
        for script in builder.generate_scripts(samples):
            writer.write(script)

    if len(vars) > 0:
        print(f"Script Variables: {' '.join(vars)}")

    print(f"Generated {samples} in {output}")


@main.command()
@click.argument(
    "data",
    type=click.Path(dir_okay=False, file_okay=True, exists=True, path_type=Path),
    nargs=-1,
)
@click.option(
    "-e",
    "--epochs",
    metavar="N",
    default=10,
    type=int,
    help="The number of training epochs.",
)
@click.option(
    "-t",
    "--threads",
    metavar="N",
    type=int,
    help="The number of threads to use.  Use's PyTorch's default if not provided.",
)
@click.option(
    "-s",
    "--seed",
    metavar="S",
    type=int,
    help="The seed used for initializing all RNGs during training.",
)
@click.pass_obj
def train_model(
    ctx: CliContext,
    data: list[Path],
    epochs: int,
    threads: int | None,
    seed: int | None,
) -> None:
    """Train a language model with some training data.

    The training data is provided in a json lines file at DATA.  A small portion
    will be reserved for validating the model after each epoch.
    """
    if len(data) == 0:
        raise click.ClickException("Missing training data!")

    samples: list[SampleData] = []
    for dataset in data:
        samples.extend(from_jsonlines(dataset))

    model = CalculatorLanguageModel(attention_heads=4, layers=6)
    trainer = ModelTrainer(samples, epochs=epochs, seed=seed)

    num_files = len(list(ctx.models.glob("*.pt")))
    model_id = f"{num_files + 1:03}"
    model_name = f"model-{model_id}.pt"

    clear_screen()

    print("Starting model training.")
    if seed is not None:
        print(f"Seed {seed}", indent=2)

    threads = torch.get_num_threads() if threads is None else threads
    torch.set_num_threads(threads)
    print(f"Storage: {ctx.models.resolve()}", indent=2)
    print(f"Threads: {threads}", indent=2)
    print(f"Model  : {model_name}", indent=2)
    print(f"Epochs : {epochs}", indent=2)

    progress = Progress(console=console)
    task_total = progress.add_task("Overall", total=epochs * trainer.training_samples)

    with Live(console=console) as live:

        def progress_callback(iter: TrainingIteration) -> None:
            if iter.iteration == 0:
                if iter.epoch > 0:
                    task_epoch = progress.task_ids[-1]
                    progress.remove_task(task_epoch)
                task_epoch = progress.add_task(
                    f"Epoch {iter.epoch}", total=trainer.training_samples
                )
            else:
                task_epoch = progress.task_ids[-1]

            progress.update(task_total, advance=1)
            progress.update(task_epoch, advance=1)

            if iter.iteration == 0 or (iter.iteration % 100) == 0:
                live.update(_update_training_display(progress, iter))

        summary = trainer.train(model, callback=progress_callback)

    # Save the trained model
    model.save(ctx.models / model_name)

    # Generate the training report
    report_path = ctx.models / f"report-{model_id}"
    _create_report(report_path, model_name, summary)


@main.command()
def repl() -> None:
    """Run the interactive command interface."""


@main.command()
@click.pass_obj
@click.confirmation_option(prompt="Remove any trained models?")
def clean(ctx: CliContext) -> None:
    """Remove any existing models in the models storage directory."""
    model_files = ctx.models.glob("*.pt")
    reports = ctx.models.glob("report-*")

    num_files = 0
    for model in model_files:
        model.unlink()
        num_files += 1

    print(f"Removed {num_files} models from {ctx.models.resolve()}.")

    num_reports = 0
    for report in reports:
        shutil.rmtree(report)
        num_reports += 1

    print(f"Removed {num_reports} reports from {ctx.models.resolve()}.")


if __name__ == "__main__":
    main()
