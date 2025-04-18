from typing import Iterator

from . import ast
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
        for line in self.parse(script):
            result = line.evaluate(self._ws)

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

    def solution_steps(self, script: str) -> Iterator[RootExpr]:
        """Generation the steps showing how the script it evaluated.

        The steps are determined by gradually reducing the complexity of a
        script's original AST.  The reduction process only evaluates an AST node
        if the child nodes are all literal values.  The reduction stops when the
        AST is a single literal node.

        Parameters
        ----------
        script : str
            input script

        Yields
        ------
        :class:`RootExpr`
            a step in solving the expression in the input script
        """
        last_output = ""
        for line in self.parse(script):
            while not isinstance(line.input, ast.NumberExpr):
                try:
                    line.input = self._simplify_ast(line.input)
                except ZeroDivisionError:
                    # This is a bit of a hack, but it allows a division-by-zero
                    # to be represented as a variable and then stop the
                    # simplification process.
                    line.input = ast.VariableExpr("DIV_BY_ZERO")
                    yield line
                    break

                # This check is because an expression like "-(1)" will end up
                # turning into multiple steps, with the first being to remove
                # the '()' and then followed by the actual result.  This isn't
                # useful so if the same result is generated, don't show it
                # twice.
                current_output = line.print()
                if current_output != last_output:
                    yield line

                last_output = current_output

    def _simplify_ast(self, expr: ast.ExprBase) -> ast.ExprBase:
        if isinstance(expr, ast._UnaryExpr):
            if isinstance(expr.input, ast._NullaryExpr):
                return ast.NumberExpr(expr.evaluate(self._ws))
            else:
                expr.input = self._simplify_ast(expr.input)
                return expr

        if isinstance(expr, ast._BinaryExpr):
            left_resolves = isinstance(expr.left, ast._NullaryExpr)
            right_resolves = isinstance(expr.right, ast._NullaryExpr)

            if left_resolves and right_resolves:
                return ast.NumberExpr(expr.evaluate(self._ws))

            if left_resolves:
                expr.right = self._simplify_ast(expr.right)
                return expr

            if right_resolves:
                expr.left = self._simplify_ast(expr.left)
                return expr

            if not (left_resolves or right_resolves):
                expr.left = self._simplify_ast(expr.left)
                return expr

        return expr
