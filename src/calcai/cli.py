from pathlib import Path

import click

from ._console import print
from .model import CalculatorLanguageModel
from .training import (
    ExpressionGenerator,
    ModelTrainer,
    SampleWriter,
    ScriptBuilder,
    TrainingIteration,
    from_jsonlines,
)


def _training_callback(iter: TrainingIteration) -> None:
    if iter.iteration != 0 and (iter.iteration % 50) != 0:
        return

    print(f"Epoch {iter.epoch} - Iteration {iter.iteration}")
    print(f"Loss = {iter.loss}", indent=2, bullet="")
    print(f"Expected = {iter.expected}", indent=2, bullet="")
    print(f"Actual   = {iter.actual}", indent=2, bullet="")


@click.group()
def main() -> None:
    """Transformer-based Calculator"""


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
    "-s",
    "--seed",
    metavar="S",
    type=int,
    help="The seed used for initializing all RNGs during training.",
)
def train_model(data: Path, epochs: int, seed: int | None) -> None:
    """Train a language model with some training data.

    The training data is provided in a json lines file at DATA.  A small portion
    will be reserved for validating the model after each epoch.
    """
    samples = list(from_jsonlines(data))
    model = CalculatorLanguageModel()
    trainer = ModelTrainer(samples, epochs=epochs, seed=seed)

    print("Starting model training.")
    if seed is not None:
        print(f"Seed {seed}", indent=2)

    trainer.train(model, callback=_training_callback)


@main.command()
def repl() -> None:
    """Run the interactive command interface."""


if __name__ == "__main__":
    main()
