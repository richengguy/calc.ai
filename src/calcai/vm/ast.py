from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Sequence, cast

from .scanner import Token, TokenType
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
    def __init__(self, input: _Expr, top: bool = False) -> None:
        super().__init__(ExpressionType.EXPRESSION, input)
        self._top = top

    @property
    def top(self) -> bool:
        return self._top

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


def _create_terminal_token(token: Token, ws: WorkingSpace) -> _Expr:
    match token.type:
        case TokenType.NUMBER:
            return NumberExpr(int(token.value))
        case TokenType.SYMBOL:
            return VariableExpr(token.value, ws)
        case _:
            raise RuntimeError(f"Did not expect a {token.value}!")


def _build_expr(
    tokens: Sequence[Token], ws: WorkingSpace, left: _Expr | None = None
) -> _Expr:
    if len(tokens) == 0:
        raise ValueError("Expected a non-empty token stream!")

    if len(tokens) == 1:
        return _create_terminal_token(tokens[0], ws)

    match tokens[0].type:
        case TokenType.NUMBER:
            left = NumberExpr(int(tokens[0].value))
            return _build_expr(tokens[1:], ws, left)
        case TokenType.SYMBOL:
            left = VariableExpr(tokens[0].value, ws)
            return _build_expr(tokens[1:], ws, left)
        case TokenType.EQUALS:
            if left is None:
                raise RuntimeError("Missing the left side of the assignment expression!")
            if left.type != ExpressionType.VARIABLE:
                raise RuntimeError(f"Expected the left side to be a variable, got a {left.type}!")

            left = cast(VariableExpr, left)
            right = _build_expr(tokens[1:], ws)

            return AssignExpr(left.key, right, ws)
        case TokenType.ADD:
            # Note: this is allowed because '+1' is the same as '1'.
            if left is None:
                return _build_expr(tokens[1:], ws)

            right = _build_expr(tokens[1:], ws)
            return AddExpr(left, right)
        case TokenType.SUBTRACT:
            if left is None:
                return NegateExpr(_build_expr(tokens[1:], ws))

            right = _build_expr(tokens[1:], ws)
            return SubtractExpr(left, right)
        case TokenType.MULTIPLY:
            if left is None:
                raise RuntimeError("Missing the left side of the multiply expression!")

            right = _build_expr(tokens[1:], ws)
            return MultiplyExpr(left, right)
        case TokenType.DIVIDE:
            if left is None:
                raise RuntimeError("Missing the left side of the divide expression!")

            right = _build_expr(tokens[1:], ws)
            return DivideExpr(left, right)
        case TokenType.POWER:
            if left is None:
                raise RuntimeError("Missing the left side of the power expression!")

            right = _build_expr(tokens[1:], ws)
            return PowerExpr(left, right)
        case TokenType.OPEN_BRACKET:
            return _build_expr(tokens[1:], ws)
        case TokenType.CLOSE_BRACKET:
            if left is None:
                raise RuntimeError("Unexpected ')'.")
            return left

    raise RuntimeError("Encountered a syntax error!")


def build_ast(tokens: Sequence[Token], ws: WorkingSpace) -> RootExpr:
    """Build up an AST from a token sequence.

    The token sequence is assumed to represent a single complete line.  The
    output is a top-level "root expression" the contains the parsed input.  Any
    whitespace tokens are filtered out prior to creating the AST.

    Parameters
    ----------
    tokens : sequence of :class:`Token`
        input token stream

    Returns
    -------
    :class:`RootExpr`
        root expression node
    """
    tokens = [t for t in tokens if t.type != TokenType.SPACE]
    expr = _build_expr(tokens, ws)
    return RootExpr(expr, True)
