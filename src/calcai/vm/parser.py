from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Protocol

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


class Expr(ABC):
    def __init__(self, type: ExpressionType) -> None:
        self._type = type

    @property
    def type(self) -> ExpressionType:
        return self._type

    @abstractmethod
    def evaluate(self) -> int:
        ...


class _UnaryExpression(Expr):
    def __init__(self, type: ExpressionType, expr: Expr) -> None:
        super().__init__(type)
        self._expr = expr

    @property
    def expr(self) -> Expr:
        return self._expr


class _BinaryExpression(Expr):
    def __init__(self, type: ExpressionType, left: Expr, right: Expr) -> None:
        super().__init__(type)
        self._left = left
        self._right = right

    @property
    def left(self) -> Expr:
        return self._left

    @property
    def right(self) -> Expr:
        return self._right


class WorkingSpace:
    """A scratch pad for storing calculation variables."""
    def __init__(self) -> None:
        self._data: dict[str, int] = dict()

    def store(self, key: str, value: int) -> None:
        self._data[key] = value

    def load(self, key: str) -> int:
        return self._data[key]


class Expression(_UnaryExpression):
    """Stores an entire input line."""
    def __init__(self, expr: Expr) -> None:
        super().__init__(ExpressionType.EXPRESSION, expr)

    def evaluate(self):
        return self.expr.evaluate()


class NumberExpression(Expr):
    """Represents a numeric constant."""
    def __init__(self, value: int) -> None:
        super().__init__(ExpressionType.NUMBER)
        self._value = value

    def evaluate(self) -> int:
        return self._value


class VariableExpression(Expr):
    """Represents some variable stored in the working space."""
    def __init__(self, key: str, ws: WorkingSpace) -> None:
        super().__init__(ExpressionType.VARIABLE)
        self._key = key
        self._ws = ws

    @property
    def name(self) -> str:
        return self._key

    def evaluate(self) -> int:
        return self._ws.load(self._key)


class AssignExpression(_UnaryExpression):
    """Represents the assignment of same value to a variable."""
    def __init__(self, key: str, ws: WorkingSpace, expr: Expr):
        super().__init__(ExpressionType.ASSIGN, expr)
        self._key = key
        self._ws = ws

    @property
    def name(self) -> str:
        return self._key

    def evaluate(self) -> int:
        value = self.expr.evaluate()
        self._ws.store(self._key, value)
        return value


class AddExpression(_BinaryExpression):
    """Add two expressions together."""
    def __init__(self, left: Expr, right: Expr):
        super().__init__(ExpressionType.ADD, left, right)

    def evaluate(self) -> int:
        return self.left.evaluate() + self.right.evaluate()


# TODO: Finish adding in the different expressions


class NegateExpression(_UnaryExpression):
    """Perform a '(-1) * x' operation."""
    def __init__(self, expr: Expr):
        super().__init__(ExpressionType.NEGATE, expr)

    def evaluate(self) -> int:
        return -self.expr.evaluate()
