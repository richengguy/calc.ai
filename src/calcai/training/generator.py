from ..vm.ast import (
    ExprBase,
    ExpressionType,
    AddExpr,
    AssignExpr,
    DivideExpr,
    MultiplyExpr,
    NegateExpr,
    NumberExpr,
    PowerExpr,
    RootExpr,
    SubtractExpr,
    VariableExpr,
)
from .data import SampleData

import random


_NODE_CHOICES = [
    ExpressionType.ADD,
    ExpressionType.SUBTRACT,
    ExpressionType.MULTIPLY,
    ExpressionType.DIVIDE,
    ExpressionType.POWER,
    ExpressionType.NEGATE,
    ExpressionType.EXPRESSION,
    ExpressionType.NUMBER,
]


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

    def generate_ast(self, depth: int, seed: int | None = None) -> str:
        """Generate a random AST.

        Parameters
        ----------
        depth : int
            the maximum depth of the AST; corresponds to an expression's
            complexity
        seed : int, optional
            specify the random seed used when generating the AST

        Returns
        -------
        :class:`RootExpr`
            AST root node
        """
        if depth < 1:
            raise ValueError("Depth must be '1' or greater.")

        prng = random.Random(seed)
        root = self._create_ast(depth, ExpressionType.EXPRESSION, prng)
        return RootExpr(root, True).print()

    def _create_ast(
        self, depth: int, parent: ExpressionType, prng: random.Random
    ) -> ExprBase:
        if depth == 0:
            value = prng.randint(self._min, self._max)
            return NumberExpr(value)

        selected = prng.choice(_NODE_CHOICES)

        # NOTE: A double negation ('--') isn't supported by the parser so some
        # extra handling is necessary to avoid this.
        if selected == ExpressionType.NEGATE and parent == ExpressionType.NEGATE:
            while selected == ExpressionType.NEGATE:
                selected = prng.choice(_NODE_CHOICES)

        match selected:
            case ExpressionType.ADD:
                left = self._create_ast(depth - 1, ExpressionType.ADD, prng)
                right = self._create_ast(depth - 1, ExpressionType.ADD, prng)
                return AddExpr(left, right)
            case ExpressionType.SUBTRACT:
                left = self._create_ast(depth - 1, ExpressionType.SUBTRACT, prng)
                right = self._create_ast(depth - 1, ExpressionType.SUBTRACT, prng)
                return SubtractExpr(left, right)
            case ExpressionType.MULTIPLY:
                left = self._create_ast(depth - 1, ExpressionType.MULTIPLY, prng)
                right = self._create_ast(depth - 1, ExpressionType.MULTIPLY, prng)
                return MultiplyExpr(left, right)
            case ExpressionType.DIVIDE:
                left = self._create_ast(depth - 1, ExpressionType.DIVIDE, prng)
                right = self._create_ast(depth - 1, ExpressionType.DIVIDE, prng)
                return DivideExpr(left, right)
            case ExpressionType.POWER:
                left = self._create_ast(depth - 1, ExpressionType.POWER, prng)
                right = self._create_ast(depth - 1, ExpressionType.POWER, prng)
                return PowerExpr(left, right)
            case ExpressionType.NEGATE:
                left = self._create_ast(depth - 1, ExpressionType.NEGATE, prng)
                return NegateExpr(left)
            case ExpressionType.EXPRESSION:
                left = self._create_ast(depth - 1, ExpressionType.EXPRESSION, prng)
                return RootExpr(left)
            case ExpressionType.NUMBER:
                return NumberExpr(prng.randint(self._min, self._max))
            case _:
                raise RuntimeError(f"Unsupported selection '{selected}'.")
