import itertools
import random
from collections.abc import Sequence
from typing import Literal, overload

from ..vm.ast import (
    AddExpr,
    AssignExpr,
    DivideExpr,
    ExprBase,
    ExpressionType,
    MultiplyExpr,
    NegateExpr,
    NumberExpr,
    RootExpr,
    SubtractExpr,
    VariableExpr,
)

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

    @overload
    def generate_expr(
        self,
        depth: int,
        seed: int | None,
        *,
        assign_to: str | None = None,
        vars: Sequence[str] | None = None,
    ) -> str:
        pass

    @overload
    def generate_expr(
        self,
        depth: int,
        seed: int | None,
        *,
        assign_to: str | None = None,
        vars: Sequence[str] | None = None,
        ret_node: Literal[True],
    ) -> RootExpr:
        pass

    def generate_expr(
        self,
        depth: int,
        seed: int | None,
        *,
        assign_to: str | None = None,
        vars: Sequence[str] | None = None,
        ret_node: bool = False,
    ) -> str | RootExpr:
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
        ret_node : bool
            set to ``True`` to return the AST node instead of a string

        Returns
        -------
        str or :class:`RootExpr`
            generated expression
        """
        if depth < 1:
            raise ValueError("Depth must be '1' or greater.")

        prng = random.Random(seed)
        root = self._create_ast(depth, ExpressionType.EXPRESSION, vars, prng)
        if assign_to is not None:
            root = AssignExpr(assign_to, root)

        expr = RootExpr(root, True)
        return expr if ret_node else expr.print()

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
        # unnecessary '((()))' situation.  The parser can handle this but it
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

                # This is necessary when the contents aren't a terminal node.
                # For example, if 'left' is "1 + 2", then this creates
                # "-(1 + 2)", which is correct, instead of "-1 + 2".
                if (
                    left.type != ExpressionType.NUMBER
                    and left.type != ExpressionType.VARIABLE
                ):
                    left = RootExpr(left)

                return NegateExpr(left)
            case ExpressionType.EXPRESSION:
                # An expression doesn't decrease the depth because it's a method
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
