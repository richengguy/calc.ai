from ..vm.ast import (
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
    """Generate valid, but random expression ASTs.

    The generator creates random expressions that can be passed into the VM
    intepreter.  This allows them to be used to generate random expressions for
    training the language model.
    """

    def __init__(
        self,
        *,
        breadth: int = 3,
        depth: int = 3,
        variables: int = 0,
        seed: int | None = None,
    ) -> None:
        """
        Parameters
        ----------
        breadth : int
            How "broad" the expression can be.  For example, the difference
            between "1 + 2" and "1 + 2 + 3".
        depth : int
            How "deep" the expression can be.  For example,
            "(5 + 2) * (1 / (3 + 2))" is deeper, or has more levels of "()"
            nestings than "(1 + 2) * 3".
        variables : int
            The number of variables an expression may have.
        seed : int or None
            The RNG seed.  If ``None`` then a random one is picked.
        """
        self.breadth = breadth
        self.depth = depth
        self.variables = variables

        if seed is None:
            import os

            value = os.urandom(4)
            self._seed = int.from_bytes(value)
        else:
            self._seed = seed

        random.seed(self._seed)

    @property
    def seed(self) -> int:
        return self._seed

    def generate(self) -> RootExpr:
        """Generate an AST.

        Returns
        -------
        :class:`RootExpr`
            the AST root node
        """
