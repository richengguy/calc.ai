from pathlib import Path

import click

from .training import ExpressionGenerator, SampleWriter, ScriptBuilder


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
def generate_data(samples: int) -> None:
    """Generate training data for the language model."""
    file = Path("samples.json")

    with SampleWriter(file) as writer:
        generator = ExpressionGenerator(25)
        builder = ScriptBuilder(generator)
        builder.set_variables(["x", "y"])
        for script in builder.generate_scripts(samples):
            writer.write(script)


@main.command()
def train_model() -> None:
    """Train a language model using automatically-generated training data."""


@main.command()
def repl() -> None:
    """Run the interactive command interface."""


if __name__ == "__main__":
    main()
