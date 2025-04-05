from pathlib import Path

import click

from ._console import print
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
@click.option(
    "-d",
    "--depth",
    metavar="N",
    default=3,
    help="Depth, or complexity, of the generated expressions."
)
@click.option(
    "-n",
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
def generate_data(samples: int, depth: int, max_value: int, vars: list[str], output: Path) -> None:
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
def train_model() -> None:
    """Train a language model using automatically-generated training data."""


@main.command()
def repl() -> None:
    """Run the interactive command interface."""


if __name__ == "__main__":
    main()
