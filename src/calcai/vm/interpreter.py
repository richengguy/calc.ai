from typing import Iterator

from .ast import RootExpr, build_ast
from .runtime import WorkingSpace
from .scanner import tokenize


class Interpreter:
    """Interpret calc.ai scripts."""

    def __init__(self):
        self._ws = WorkingSpace()

    @property
    def working_space(self) -> WorkingSpace:
        """Working space for any script variables."""
        return self._ws

    def run(self, script: str) -> int:
        """Run the given script.

        Parameters
        ----------
        script : str
            input script

        Returns
        -------
        int
            result of the calculation
        """
        result: int | None = None
        for ast in self.parse(script):
            result = ast.evaluate(self._ws)

        if result is None:
            raise RuntimeError("There was no result to return!")

        return result

    def parse(self, script: str) -> Iterator[RootExpr]:
        """Parse the script but don't execute it.

        This returns a list of ASTs, one per line in the script.

        Parameters
        ----------
        script : str
            input script

        Yields
        ------
        :class:`RootExpr`
            root AST node
        """
        lines = script.splitlines()
        for line in lines:
            line = line.strip()
            if len(line) == 0:
                continue
            try:
                yield build_ast(tokenize(line))
            except Exception as e:
                raise RuntimeError(f"Could not parse '{line}'.") from e
