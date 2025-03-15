from collections.abc import Sequence
from typing import Iterator, cast

from ..vm import Interpreter
from ..vm.ast import AssignExpr, ExprBase, ExpressionType, VariableExpr
from .data import SampleData
from .generator import ExpressionGenerator


def _collect_vars(node: ExprBase) -> set[str]:
    var_names: set[str] = set()

    if node.type == ExpressionType.VARIABLE:
        node = cast(VariableExpr, node)
        return set([node.key])

    if hasattr(node, "left") and hasattr(node, "right"):
        var_names.update(_collect_vars(node.left))
        var_names.update(_collect_vars(node.right))
        return var_names

    if hasattr(node, "input"):
        var_names.update(_collect_vars(node.input))
        return var_names

    return set()


class ScriptBuilder:
    """Builds a VM script for training a language model."""

    def __init__(
        self,
        generator: ExpressionGenerator,
        *,
        expr_depth: int = 3,
        assign_depth: int = 1,
    ) -> None:
        """
        Parameters
        ----------
        generator : :class:`ExpressionGenerator`
            configured expression generator
        expr_depth : int
            the complexity of general expressions
        assign_depth : int
            the complexity of variable assignment expressions
        """
        self._g = generator
        self._assign_depth = assign_depth
        self._expr_depth = expr_depth
        self._seed = 0
        self._vars: list[str] | None = None

    def reset(self) -> None:
        """Reset the internal state."""
        self._seed = 0

    def set_variables(self, vars: Sequence[str]) -> None:
        """Set the variable names to use when building an expression script.

        Parameters
        ----------
        vars : str sequence
            list of variable names; set to ``[]`` if no variables are used
        """
        if len(vars) == 0:
            self._vars = None
        else:
            self._vars = list(vars)

    def generate_scripts(self, num_scripts: int) -> Iterator[SampleData]:
        """Randomly generate a set of scripts.

        Parameters
        ----------
        num_scripts : int
            the number of scripts to generate

        Yields
        ------
        :class:`SampleData`
            the script and its result
        """
        for _ in range(num_scripts):
            init_seed = self._seed
            expr = self._g.generate_expr(
                self._expr_depth, self._seed, vars=self._vars, ret_node=True
            )
            self._seed += 1

            lines: list[str] = []
            if self._vars is not None:
                expr_vars = _collect_vars(expr)
                for var in expr_vars:
                    assign_eqn = self._g.generate_expr(
                        self._assign_depth, self._seed, ret_node=True
                    )
                    self._seed += 1
                    lines.append(AssignExpr(var, assign_eqn).print())

            lines.append(expr.print())
            script = "\n".join(lines)
            try:
                vm = Interpreter()
                result = vm.run(script)
            except ZeroDivisionError:
                result = None
            except RuntimeError as e:
                raise RuntimeError(f"[{init_seed}] -> {e}") from e

            yield SampleData(init_seed, script, result)
