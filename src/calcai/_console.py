from rich.console import Console

console = Console()


def print(msg: str, *, bullet: str = ":arrow_forward:", indent: int = 0) -> None:
    """Print a message to the console.

    Parameters
    ----------
    msg : str
        message to print
    bullet : str
        the short string shown in front the message
    indent : int
        indentation, in characters
    """
    console.print(f"{' '*indent} {bullet} {msg}", highlight=False)
