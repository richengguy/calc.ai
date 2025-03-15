from pathlib import Path

import click

from ._console import print
from .training import ExpressionGenerator, SampleWriter, ScriptBuilder

_TRAINING_DATA = Path("samples.jsonl")


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
    "--max",
    "max_value",
    metavar="N",
    default=25,
    help="Maximum integer value in any generated expression.",
)
@click.option("--variable", "-v", multiple=True)
def generate_data(samples: int, max_value: int) -> None:
    """Generate training data for the language model."""
    with SampleWriter(_TRAINING_DATA) as writer:
        generator = ExpressionGenerator(max_value)
        builder = ScriptBuilder(generator)
        builder.set_variables(["x", "y"])
        for script in builder.generate_scripts(samples):
            writer.write(script)

    print(f"Generated {samples} in {_TRAINING_DATA}")


@main.command()
def train_model() -> None:
    """Train a language model using automatically-generated training data."""


@main.command()
def repl() -> None:
    """Run the interactive command interface."""


if __name__ == "__main__":
    main()
