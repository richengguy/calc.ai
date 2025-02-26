from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Sequence

from .runtime import WorkingSpace
from .scanner import Token, TokenType


class ExpressionType(int, Enum):
    """Set of operations the calculator VM can perform."""

    EXPRESSION = auto()
    """A complete expression that will evaluate down into a number."""

    NUMBER = auto()
    """Some integer value."""

    VARIABLE = auto()
    """A variable that stores some integer."""

    ASSIGN = auto()
    """Assigns a numerical value into a variable for later use."""

    ADD = auto()
    """Add two values together."""

    SUBTRACT = auto()
    """Subtract one value from another."""

    MULTIPLY = auto()
    """Multiply two values together."""

    DIVIDE = auto()
    """Divide one value from another (note: the VM only does integer operations)."""

    POWER = auto()
    """Compute the value of a number to some power."""

    NEGATE = auto()
    """Multiply the given value with '-1'."""


class _Op(ABC):
    def __init__(self, type: ExpressionType, args: Sequence[str]) -> None:
        self._type = type
        self._args = list(args)

    @property
    def type(self) -> ExpressionType:
        return self._type

    @property
    def args(self) -> list[str]:
        return self._args


class _NullaryOp(_Op):
    @abstractmethod
    def evaluate(self, **kwargs) -> int:
        ...


class _UnaryOp(_Op):
    @abstractmethod
    def evaluate(self, left: int, **kwargs) -> int:
        ...


class _BinaryOp(_Op):
    @abstractmethod
    def evaluate(self, left: int, right: int, **kwargs) -> int:
        ...


class NumberExpr(_NullaryOp):
    def __init__(self):
        super().__init__(ExpressionType.NUMBER, ["value"])

    def evaluate(self, *, value: int) -> int:
        return value


class Variable(_NullaryOp):
    def __init__(self, key: str) -> None:
        super().__init__(ExpressionType.VARIABLE, ["key"])
        self.key = key
