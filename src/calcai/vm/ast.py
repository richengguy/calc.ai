from abc import ABC, abstractmethod
from enum import Enum, auto

from .runtime import WorkingSpace


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


class _Expr(ABC):
    def __init__(self, type: ExpressionType) -> None:
        self._type = type

    @property
    def type(self) -> ExpressionType:
        return self._type

    @abstractmethod
    def evaluate(self) -> int: ...


class _NullaryExpr(_Expr): ...


class _UnaryExpr(_Expr):
    def __init__(self, type: ExpressionType, input: _Expr) -> None:
        super().__init__(type)
        self._input = input

    @property
    def input(self) -> _Expr:
        return self._input


class _BinaryExpr(_Expr):
    def __init__(self, type: ExpressionType, left: _Expr, right: _Expr) -> None:
        super().__init__(type)
        self._left = left
        self._right = right

    @property
    def left(self) -> _Expr:
        return self._left

    @property
    def right(self) -> _Expr:
        return self._right


# Top-level Expression


class RootExpr(_UnaryExpr):
    def __init__(self, input: _Expr) -> None:
        super().__init__(ExpressionType.EXPRESSION, input)

    def evaluate(self):
        return self.input.evaluate()


# Arithmetic Expressions


class AddExpr(_BinaryExpr):
    def __init__(self, left: _Expr, right: _Expr) -> None:
        super().__init__(ExpressionType.ADD, left, right)

    def evaluate(self) -> int:
        return self.left.evaluate() + self.right.evaluate()


class SubtractExpr(_BinaryExpr):
    def __init__(self, left: _Expr, right: _Expr) -> None:
        super().__init__(ExpressionType.SUBTRACT, left, right)

    def evaluate(self) -> int:
        return self.left.evaluate() - self.right.evaluate()


class MultiplyExpr(_BinaryExpr):
    def __init__(self, left: _Expr, right: _Expr) -> None:
        super().__init__(ExpressionType.MULTIPLY, left, right)

    def evaluate(self) -> int:
        return self.left.evaluate() * self.right.evaluate()


class DivideExpr(_BinaryExpr):
    def __init__(self, left: _Expr, right: _Expr) -> None:
        super().__init__(ExpressionType.DIVIDE, left, right)

    def evaluate(self) -> int:
        return self.left.evaluate() // self.right.evaluate()


class PowerExpr(_BinaryExpr):
    def __init__(self, left: _Expr, right: _Expr) -> None:
        super().__init__(ExpressionType.POWER, left, right)

    def evaluate(self) -> int:
        return self.left.evaluate() ** self.right.evaluate()


class NegateExpr(_UnaryExpr):
    def __init__(self, input: _Expr) -> None:
        super().__init__(ExpressionType.NEGATE, input)

    def evaluate(self) -> int:
        return -self.input.evaluate()


# Data Expressions


class NumberExpr(_NullaryExpr):
    def __init__(self, value: int) -> None:
        super().__init__(ExpressionType.NUMBER)
        self.value = value

    def evaluate(self) -> int:
        return self.value


class VariableExpr(_NullaryExpr):
    def __init__(self, key: str, ws: WorkingSpace) -> None:
        super().__init__(ExpressionType.VARIABLE)
        self.key = key
        self._ws = ws

    def evaluate(self) -> int:
        return self._ws.load(self.key)


class AssignExpr(_UnaryExpr):
    def __init__(self, key: str, input: _Expr, ws: WorkingSpace) -> None:
        super().__init__(ExpressionType.ASSIGN, input)
        self.key = key
        self._ws = ws

    def evaluate(self) -> int:
        value = self.input.evaluate()
        self._ws.store(self.key, value)
        return value
