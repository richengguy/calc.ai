from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Sequence

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


class ExprBase(ABC):
    def __init__(self, type: ExpressionType) -> None:
        self._type = type

    @property
    def type(self) -> ExpressionType:
        return self._type

    @abstractmethod
    def evaluate(self, ws: WorkingSpace) -> int: ...

    @abstractmethod
    def print(self) -> str: ...


class _NullaryExpr(ExprBase): ...


class _UnaryExpr(ExprBase):
    def __init__(self, type: ExpressionType, input: ExprBase) -> None:
        super().__init__(type)
        self._input = input

    @property
    def input(self) -> ExprBase:
        return self._input


class _BinaryExpr(ExprBase):
    def __init__(self, type: ExpressionType, left: ExprBase, right: ExprBase) -> None:
        super().__init__(type)
        self._left = left
        self._right = right

    @property
    def left(self) -> ExprBase:
        return self._left

    @property
    def right(self) -> ExprBase:
        return self._right


# Top-level Expression


class RootExpr(_UnaryExpr):
    def __init__(self, input: ExprBase, top: bool = False) -> None:
        super().__init__(ExpressionType.EXPRESSION, input)
        self._top = top

    @property
    def top(self) -> bool:
        return self._top

    def evaluate(self, ws: WorkingSpace) -> int:
        return self.input.evaluate(ws)

    def print(self) -> str:
        interior = self.input.print()
        if self.top:
            return interior
        else:
            return f"({interior})"


# Arithmetic Expressions


class AddExpr(_BinaryExpr):
    def __init__(self, left: ExprBase, right: ExprBase) -> None:
        super().__init__(ExpressionType.ADD, left, right)

    def evaluate(self, ws: WorkingSpace) -> int:
        return self.left.evaluate(ws) + self.right.evaluate(ws)

    def print(self) -> str:
        return f"{self.left.print()} + {self.right.print()}"


class SubtractExpr(_BinaryExpr):
    def __init__(self, left: ExprBase, right: ExprBase) -> None:
        super().__init__(ExpressionType.SUBTRACT, left, right)

    def evaluate(self, ws: WorkingSpace) -> int:
        return self.left.evaluate(ws) - self.right.evaluate(ws)

    def print(self) -> str:
        return f"{self.left.print()} - {self.right.print()}"


class MultiplyExpr(_BinaryExpr):
    def __init__(self, left: ExprBase, right: ExprBase) -> None:
        super().__init__(ExpressionType.MULTIPLY, left, right)

    def evaluate(self, ws: WorkingSpace) -> int:
        return self.left.evaluate(ws) * self.right.evaluate(ws)

    def print(self) -> str:
        return f"{self.left.print()} * {self.right.print()}"


class DivideExpr(_BinaryExpr):
    def __init__(self, left: ExprBase, right: ExprBase) -> None:
        super().__init__(ExpressionType.DIVIDE, left, right)

    def evaluate(self, ws: WorkingSpace) -> int:
        return self.left.evaluate(ws) // self.right.evaluate(ws)

    def print(self) -> str:
        return f"{self.left.print()} / {self.right.print()}"


class PowerExpr(_BinaryExpr):
    def __init__(self, left: ExprBase, right: ExprBase) -> None:
        super().__init__(ExpressionType.POWER, left, right)

    def evaluate(self, ws: WorkingSpace) -> int:
        return self.left.evaluate(ws) ** self.right.evaluate(ws)

    def print(self) -> str:
        return f"{self.left.print()} ^ {self.right.print()}"


class NegateExpr(_UnaryExpr):
    def __init__(self, input: ExprBase) -> None:
        super().__init__(ExpressionType.NEGATE, input)

    def evaluate(self, ws: WorkingSpace) -> int:
        return -self.input.evaluate(ws)

    def print(self) -> str:
        return f"-{self.input.print()}"


# Data Expressions


class NumberExpr(_NullaryExpr):
    def __init__(self, value: int) -> None:
        super().__init__(ExpressionType.NUMBER)
        self.value = value

    def evaluate(self, ws: WorkingSpace) -> int:
        return self.value

    def print(self) -> str:
        return str(self.value)


class VariableExpr(_NullaryExpr):
    def __init__(self, key: str) -> None:
        super().__init__(ExpressionType.VARIABLE)
        self.key = key

    def evaluate(self, ws: WorkingSpace) -> int:
        return ws.load(self.key)

    def print(self) -> str:
        return self.key


class AssignExpr(_UnaryExpr):
    def __init__(self, key: str, input: ExprBase) -> None:
        super().__init__(ExpressionType.ASSIGN, input)
        self.key = key

    def evaluate(self, ws: WorkingSpace) -> int:
        value = self.input.evaluate(ws)
        ws.store(self.key, value)
        return value

    def print(self) -> str:
        return f"{self.key} = {self.input.print()}"


def _create_terminal_expr(token: Token) -> ExprBase | None:
    match token.type:
        case TokenType.NUMBER:
            return NumberExpr(int(token.value))
        case TokenType.SYMBOL:
            return VariableExpr(token.value)
        case _:
            return None


def _create_unary_expr(tokens: Sequence[Token]) -> tuple[ExprBase, Sequence[Token]]:
    if len(tokens) == 0:
        raise ValueError("There are no tokens to process!")

    # Check if the first token is a '+' or '-' since '+1' or '-4' is valid
    # syntax.
    has_prefix = tokens[0].type == TokenType.ADD or tokens[0].type == TokenType.SUBTRACT
    is_negate = tokens[0].type == TokenType.SUBTRACT

    if has_prefix:
        if len(tokens) < 2:
            raise RuntimeError("Input is shorter than expected!")
        tokens = tokens[1:]

    if tokens[0].type == TokenType.OPEN_BRACKET:
        expr, remaining = _create_addsub_expr(tokens[1:])
        if len(remaining) == 0 or remaining[0].type != TokenType.CLOSE_BRACKET:
            raise RuntimeError("Missing a ')'!")

        expr = RootExpr(expr)
        remaining = remaining[1:]
        if is_negate:
            return NegateExpr(expr), remaining
        else:
            return expr, remaining

    if terminal := _create_terminal_expr(tokens[0]):
        if is_negate:
            terminal = NegateExpr(terminal)
        return terminal, tokens[1:]

    raise RuntimeError("Could not parse expression!")


def _create_exp_expr(tokens: Sequence[Token]) -> tuple[ExprBase, Sequence[Token]]:
    if len(tokens) == 0:
        raise ValueError("There are no tokens to process!")

    left, remaining = _create_unary_expr(tokens)
    while len(remaining) > 0:
        type = remaining[0].type
        match type:
            case TokenType.POWER:
                right, remaining = _create_unary_expr(remaining[1:])
                left = PowerExpr(left, right)
            case _:
                break

    return left, remaining


def _create_muldiv_expr(tokens: Sequence[Token]) -> tuple[ExprBase, Sequence[Token]]:
    if len(tokens) == 0:
        raise ValueError("There are no tokens to process!")

    left, remaining = _create_exp_expr(tokens)
    while len(remaining) > 0:
        type = remaining[0].type
        match type:
            case TokenType.MULTIPLY:
                right, remaining = _create_exp_expr(remaining[1:])
                left = MultiplyExpr(left, right)
            case TokenType.DIVIDE:
                right, remaining = _create_exp_expr(remaining[1:])
                left = DivideExpr(left, right)
            case _:
                break

    return left, remaining


def _create_addsub_expr(tokens: Sequence[Token]) -> tuple[ExprBase, Sequence[Token]]:
    if len(tokens) == 0:
        raise ValueError("There are no tokens to process!")

    left, remaining = _create_muldiv_expr(tokens)
    while len(remaining) > 0:
        type = remaining[0].type
        match type:
            case TokenType.ADD:
                right, remaining = _create_muldiv_expr(remaining[1:])
                left = AddExpr(left, right)
            case TokenType.SUBTRACT:
                right, remaining = _create_muldiv_expr(remaining[1:])
                left = SubtractExpr(left, right)
            case _:
                break

    return left, remaining


def build_ast(tokens: Sequence[Token]) -> RootExpr:
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
    num_tokens = len(tokens)

    if num_tokens == 0:
        raise ValueError("Expected a token stream with non-whitespace characters.")

    # Determine if this is an assignment expression.  This needs to be handled
    # here since the "var =" syntax can only appear once in a token stream.
    is_assignment = (
        num_tokens > 2
        and tokens[0].type == TokenType.SYMBOL
        and tokens[1].type == TokenType.EQUALS
    )
    if is_assignment:
        value_expr, remaining = _create_addsub_expr(tokens[2:])
        expr: ExprBase = AssignExpr(tokens[0].value, value_expr)
    else:
        expr, remaining = _create_addsub_expr(tokens)

    if len(remaining) != 0:
        raise RuntimeError("Some tokens weren't processed!")

    return RootExpr(expr, True)
