import click


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


@main.command()
def train_model() -> None:
    """Train a language model using automatically-generated training data."""


@main.command()
def repl() -> None:
    """Run the interactive command interface."""


if __name__ == "__main__":
    main()
