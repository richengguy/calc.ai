from dataclasses import dataclass
from pathlib import Path

import click
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
    SampleWriter,
    ScriptBuilder,
    TrainingIteration,
    from_jsonlines,
)


def _update_training_display(progress: Progress, iter: TrainingIteration) -> Table:
    model = Table(expand=True, show_header=False, box=box.MINIMAL)
    model.add_row(f"Expected » {iter.expected}")
    model.add_row(f"Actual   » {iter.actual}")
    model.add_section()
    model.add_row(f"Loss     » {iter.loss}")

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
    "--variable",
    "-v",
    "vars",
    multiple=True,
    help="Specify a possible variable name.  Can be repeated.",
)
@click.argument("output", type=click.Path(path_type=Path))
def generate_data(
    samples: int, depth: int, max_value: int, vars: list[str], output: Path
) -> None:
    """Generate training data for the language model.

    The training data is saved into OUTPUT as a JSONL file, where each line is a
    single JSON object.
    """
    with SampleWriter(output) as writer:
        generator = ExpressionGenerator(max_value)
        builder = ScriptBuilder(generator, expr_depth=depth)
        builder.set_variables(vars)
        for script in builder.generate_scripts(samples):
            writer.write(script)

    if len(vars) > 0:
        print(f"Script Variables: {' '.join(vars)}")

    print(f"Generated {samples} in {output}")


@main.command()
@click.argument(
    "data", type=click.Path(dir_okay=False, file_okay=True, exists=True, path_type=Path)
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
    ctx: CliContext, data: Path, epochs: int, threads: int | None, seed: int | None
) -> None:
    """Train a language model with some training data.

    The training data is provided in a json lines file at DATA.  A small portion
    will be reserved for validating the model after each epoch.
    """
    samples = list(from_jsonlines(data))
    model = CalculatorLanguageModel()
    trainer = ModelTrainer(samples, epochs=epochs, seed=seed)

    num_files = len(list(ctx.models.glob("*.pt")))
    model_name = f"model-{num_files + 1:03}.pt"

    clear_screen()

    print("Starting model training.")
    if seed is not None:
        print(f"Seed {seed}", indent=2)

    threads = torch.get_num_threads() if threads is None else threads
    torch.set_num_threads(threads)
    print(f"Storage: {ctx.models.resolve()}", indent=2)
    print(f"Threads: {threads}", indent=2)
    print(f"Model  : {model_name}", indent=2)

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

        trainer.train(model, callback=progress_callback)

    # Save the trained model
    model.save(ctx.models / model_name)


@main.command()
def repl() -> None:
    """Run the interactive command interface."""


@main.command()
@click.pass_obj
@click.confirmation_option(prompt="Remove any trained models?")
def clean(ctx: CliContext) -> None:
    """Remove any existing models in the models storage directory."""
    model_files = ctx.models.glob("*.pt")

    num_files = 0
    for model in model_files:
        model.unlink()
        num_files += 1

    print(f"Removed {num_files} from {ctx.models.resolve()}.")


if __name__ == "__main__":
    main()
