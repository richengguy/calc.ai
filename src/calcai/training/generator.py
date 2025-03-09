from ..vm.ast import (
    ExprBase,
    ExpressionType,
    AddExpr,
    AssignExpr,
    DivideExpr,
    MultiplyExpr,
    NegateExpr,
    NumberExpr,
    RootExpr,
    SubtractExpr,
    VariableExpr,
)

import random
import itertools
from collections.abc import Sequence


_NODE_CHOICES = [
    ExpressionType.ADD,
    ExpressionType.SUBTRACT,
    ExpressionType.MULTIPLY,
    ExpressionType.DIVIDE,
    ExpressionType.NEGATE,
    ExpressionType.EXPRESSION,
    ExpressionType.NUMBER,
]


# fmt: off
_NODE_WEIGHTS = [
    4,
    4,
    2,
    1,
    3,
    3,
    2
]
# fmt: on

_NODE_CUM_WEIGHTS = list(itertools.accumulate(_NODE_WEIGHTS))


class ExpressionGenerator:
    """Generate a random expression.

    The expression generator uses a simple recursive algorithm to build up
    an arithmetic expression.  The complexity of the expression is controlled
    by it maximum depth, as the underlying AST is (generally) an unbalanced
    binary tree.  The deeper the tree, the more complex the expression.
    """

    def __init__(self, max_value: int, min_value: int = 0) -> None:
        """
        Parameters
        ----------
        max_value : int
            maximum allowed value for a terminal node
        min_value : int
            minimum allowed value for a terminal node
        """
        if max_value <= min_value:
            raise ValueError("Maximum value must be greater than the minimum value.")

        if min_value < 0 or max_value < 0:
            raise ValueError("The maximum/minimum values cannot be negative.")

        self._min = min_value
        self._max = max_value

    def generate_expr(
        self,
        depth: int,
        seed: int | None,
        *,
        assign_to: str | None = None,
        vars: Sequence[str] | None = None,
    ) -> str:
        """Generate a random expression.

        Parameters
        ----------
        depth : int
            the maximum depth of the AST; corresponds to an expression's
            complexity
        seed : int
            specify the random seed used when generating the AST; a random seed
            is used when this is `None`
        assign_to : str, optional
            if set then the generated expression is an assignment
        vars : sequence of str
            names of variables to use in the expressions, along with numerical
            values

        Returns
        -------
        str
            generated expression
        """
        if depth < 1:
            raise ValueError("Depth must be '1' or greater.")

        prng = random.Random(seed)
        root = self._create_ast(depth, ExpressionType.EXPRESSION, vars, prng)
        if assign_to is not None:
            root = AssignExpr(assign_to, root)
        return RootExpr(root, True).print()

    def _create_ast(
        self,
        depth: int,
        parent: ExpressionType,
        vars: Sequence[str] | None,
        prng: random.Random,
    ) -> ExprBase:
        if depth == 0:
            return self._create_terminal(vars, prng)

        selected = prng.choices(_NODE_CHOICES, cum_weights=_NODE_CUM_WEIGHTS)[0]

        # Do another selection if the parent is an expression to avoid an
        # unnecessary '((()))' situation.  The parse can handle this but it
        # doesn't convey anything useful.  It also avoids an infinite recursion
        # situation.
        if (
            selected == ExpressionType.EXPRESSION
            and parent == ExpressionType.EXPRESSION
        ):
            while selected == ExpressionType.EXPRESSION:
                selected = prng.choices(_NODE_CHOICES, cum_weights=_NODE_CUM_WEIGHTS)[0]

        # NOTE: A double negation ('--') isn't supported by the parser so some
        # extra handling is necessary to avoid this.
        if selected == ExpressionType.NEGATE and parent == ExpressionType.NEGATE:
            while selected == ExpressionType.NEGATE:
                selected = prng.choices(_NODE_CHOICES, cum_weights=_NODE_CUM_WEIGHTS)[0]

        match selected:
            case ExpressionType.ADD:
                left = self._create_ast(depth - 1, ExpressionType.ADD, vars, prng)
                right = self._create_ast(depth - 1, ExpressionType.ADD, vars, prng)
                return AddExpr(left, right)
            case ExpressionType.SUBTRACT:
                left = self._create_ast(depth - 1, ExpressionType.SUBTRACT, vars, prng)
                right = self._create_ast(depth - 1, ExpressionType.SUBTRACT, vars, prng)
                return SubtractExpr(left, right)
            case ExpressionType.MULTIPLY:
                left = self._create_ast(depth - 1, ExpressionType.MULTIPLY, vars, prng)
                right = self._create_ast(depth - 1, ExpressionType.MULTIPLY, vars, prng)
                return MultiplyExpr(left, right)
            case ExpressionType.DIVIDE:
                left = self._create_ast(depth - 1, ExpressionType.DIVIDE, vars, prng)
                right = self._create_ast(depth - 1, ExpressionType.DIVIDE, vars, prng)
                return DivideExpr(left, right)
            case ExpressionType.NEGATE:
                left = self._create_ast(depth - 1, ExpressionType.NEGATE, vars, prng)
                return NegateExpr(left)
            case ExpressionType.EXPRESSION:
                # As expression doesn't decrease the depth because it's a method
                # for prioritizing calculations.  It's possible to remove them
                # from AST and still have the same result.
                left = self._create_ast(depth, ExpressionType.EXPRESSION, vars, prng)
                return RootExpr(left)
            case ExpressionType.NUMBER:
                return self._create_terminal(vars, prng)
            case _:
                raise RuntimeError(f"Unsupported selection '{selected}'.")

    def _create_terminal(
        self, vars: Sequence[str] | None, prng: random.Random
    ) -> ExprBase:
        var_name: str | None = None
        if vars is not None:
            select_var = prng.choice([True, False])
            if select_var:
                var_name = prng.choice(vars)

        if var_name is None:
            return NumberExpr(prng.randint(self._min, self._max))
        else:
            return VariableExpr(var_name)
