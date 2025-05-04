import shutil
from dataclasses import dataclass
from pathlib import Path

import click
import torch

from ._console import console, print
from .model import CalculatorLanguageModel
from .repl import Repl
from .training import (
    ExpressionGenerator,
    ModelTrainer,
    SampleData,
    SampleWriter,
    ScriptBuilder,
    SessionReport,
    StatusDisplay,
    from_jsonlines,
)


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
@click.option(
    "--numbers-only",
    is_flag=True,
    help=(
        "Only generate samples that are 'x = x'.  All integers between '-max' "
        "and 'max' are generated."
    ),
)
@click.argument("output", type=click.Path(path_type=Path))
def generate_data(
    samples: int,
    depth: int,
    max_value: int,
    vars: list[str],
    generate_solutions: bool,
    numbers_only: bool,
    output: Path,
) -> None:
    """Generate training data for the language model.

    The training data is saved into OUTPUT as a JSONL file, where each line is a
    single JSON object.
    """
    if numbers_only:
        with SampleWriter(output) as writer:
            writer.write(SampleData(0, "0", None, 0))
            for i in range(1, max_value + 1):
                writer.write(SampleData(2 * i - 1, f"{i}", None, i))
                writer.write(SampleData(2 * i, f"{-i}", None, -i))

        print(f"Generated samples between {-max_value} and {max_value}")
        return

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
@click.option(
    "-r",
    "--retrain",
    "model_file",
    metavar="MODEL",
    type=click.Path(dir_okay=False, file_okay=True, exists=True, path_type=Path),
    help=(
        "Retrain (really, fine-tune) a model on another data set.  The "
        "original model file is not modified."
    ),
)
@click.option(
    "--cuda",
    "use_cuda",
    is_flag=True,
    help=(
        "Use CUDA for training.  This is off by default and will fall back to "
        "the CPU if CUDA isn't supported."
    ),
)
@click.pass_obj
def train_model(
    ctx: CliContext,
    data: list[Path],
    epochs: int,
    threads: int | None,
    seed: int | None,
    model_file: Path | None,
    use_cuda: bool,
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

    device = torch.device("cpu")
    if use_cuda:
        if torch.cuda.is_available():
            device = torch.device("cuda")
        else:
            print("[bold yellow]Warning:[/] CUDA is not available.")

    if model_file is None:
        model = CalculatorLanguageModel(attention_heads=4, layers=6, device=device)
    else:
        model = CalculatorLanguageModel.load(model_file)
    trainer = ModelTrainer(samples, epochs=epochs, seed=seed, device=device)

    num_files = len(list(ctx.models.glob("*.pt")))
    model_id = f"{num_files + 1:03}"
    model_name = f"model-{model_id}.pt"

    print("Starting model training.")

    threads = torch.get_num_threads() if threads is None else threads
    torch.set_num_threads(threads)

    with StatusDisplay(console, epochs, trainer.training_samples) as status:

        if seed is not None:
            status.print(f"Seed    : {seed}")

        if model_file is not None:
            status.print(f"Retrain : {model_file}")

        status.print(f"Storage : {ctx.models.resolve()}")
        status.print(f"Model   : {model_name}")
        status.print(f"Device  : {device.type}")
        status.print(f"Threads : {threads}")
        status.print(f"Epochs  : {epochs}")
        status.print("Data    :")
        for dataset in data:
            status.print(f"  :arrow_forward: {dataset}")

        summary = trainer.train(model, callback=status.update)

    # Save the trained model
    model.save(ctx.models / model_name)

    # Generate the training report
    report_path = ctx.models / f"report-{model_id}"
    report = SessionReport()
    output = report.write(model_name, summary, report_path)
    print(f"Saved report to {output}")
    print("Training Results:")
    print(f"      Loss : {summary.validation_loss[-1]}", indent=2)
    print(f"  Accuracy : {100 * summary.validation_accuracy[-1][0]:.3g}%", indent=2)
    print(f"   Invalid : {100 * summary.validation_accuracy[-1][1]:.3g}%", indent=2)


@main.command()
@click.option(
    "-m",
    "--model",
    "model_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    help="Trained CLM the REPL will interact with.",
)
@click.pass_obj
def repl(ctx: CliContext, model_file: Path | None) -> None:
    """Run the interactive command interface."""
    if model_file is None:
        print(f"Looking for model in '{ctx.models}'.")
        files = sorted(list(ctx.models.glob("*.pt")))
        if len(files) == 0:
            raise click.ClickException(
                f"Cannot start REPL; '{ctx.models}' directory is empty!"
            )
        model_file = files[-1]

    print(f"Using {model_file}")

    model = CalculatorLanguageModel.load(model_file)

    repl = Repl(model)
    repl.launch()


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
