from ..vm.ast import (
    ExprBase,
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


class AstGenerator:
    """Generate a random expression ASTs.

    The AST generator will create a random arthimetic expression of a given
    breath and depth.  These refer to how an expression is constructed and
    evaluated using BEDMAS rules.  It does not describe the AST, which is always
    a binary tree.

    Any expression consisting solely of additions and substractions can be
    evaludated in any order.  So, the "breadth" is defined to be number addition
    and subtraction options at any level of the expression.  For instance, the
    breadth of `1 + 2` is "1", `1 + 2 - 3` is "2".  The depth is "1" for reasons
    described below.

    The remaining operations, brackets, exponents, multiplication, and division,
    all change the depth of an expression.  This is due to precendence rules
    requiring them to be evaluated in a specific order.  For example, consider
    `1 + 2 * 3`.  The `*` must be evaluated first and then the `+`.  This causes
    the expression to have a depth of "2" and a breadth of "1".  Similarly,
    `1 + (2 - 3)` also has a depth of "2" and breadth of "1" because the `()`
    forces the `2 - 3` to be evaluated first.
    """

    def __init__(self, min_value: int, max_value: int) -> None:
        self._min = min_value
        self._max = max_value

    def generate_ast(self, breadth: int, depth: int, ragged: bool = True) -> RootExpr:
        """Generate an AST root node.

        Parameters
        ----------
        breadth : int
            expression breadth; must be 1 or higher
        depth : int
            expression depth; must be 1 or higher
        ragged : bool
            if `True` then the breadth may be lower than the specified amount
            when building up sub-expressions

        Returns
        -------
        :class:`RootExpr`
            AST root node
        """
        if breadth < 1:
            raise ValueError("Breadth must be at least '1'.")
        if depth < 1:
            raise ValueError("Depth must be at least '1'.")

        return RootExpr(self._build_expr(breadth, depth - 1, 0, ragged), True)

    def _build_expr(
        self, breadth: int, max_depth: int, current_depth: int, ragged: bool
    ) -> ExprBase:
        if max_depth == current_depth:
            expr: ExprBase | None = None
            for _ in range(breadth):
                expr = self._create_add_sub_expr(expr)

            assert expr is not None
            return expr

        raise NotImplementedError()

    def _create_add_sub_expr(self, left: ExprBase | None) -> AddExpr | SubtractExpr:
        if left is None:
            left = NumberExpr(random.randint(self._min, self._max))
        right = NumberExpr(random.randint(self._min, self._max))

        pick_add = random.randint(0, 1) == 1
        if pick_add:
            return AddExpr(left, right)
        else:
            return SubtractExpr(left, right)
