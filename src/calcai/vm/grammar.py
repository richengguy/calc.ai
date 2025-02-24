from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Set of tokens the calculator VM can recognize."""

    NUMBER = auto()
    """Token is an integer number."""

    SYMBOL = auto()
    """Token is an identifier that contains only lower-case letters and (optionally) numbers."""

    ADD = auto()
    """Token is a '+'."""

    SUBTRACT = auto()
    """Token is a '-'."""

    MULTIPLY = auto()
    """Token is a '*'."""

    DIVIDE = auto()
    """Token is a "/'."""

    POWER = auto()
    """Token is a '^'."""

    OPEN_BRACKET = auto()
    """Token is an opening bracket '('."""

    CLOSE_BRACKET = auto()
    """Token is a closing bracket ')'."""

    EQUALS = auto()
    """Token is an '=' symbol, which also acts as an assignment operation."""


@dataclass(frozen=True)
class Token:
    """Represents a single token."""

    type: TokenType
    """The token's type."""

    value: str
    """The token's value."""


__DEFAULT_TOKENS: dict[str, Token] = {
    '+': Token(TokenType.ADD, '+'),
    '-': Token(TokenType.SUBTRACT, '-'),
    '*': Token(TokenType.MULTIPLY, '*'),
    '/': Token(TokenType.DIVIDE, '/'),
    '^': Token(TokenType.POWER, '^'),
    '(': Token(TokenType.OPEN_BRACKET, '('),
    ')': Token(TokenType.CLOSE_BRACKET, ')')
}


def tokenize(string: str) -> list[Token]:
    """Tokenize a string.

    Parameters
    ----------
    string : str
        input string

    Returns
    -------
    list of :class:`Token`
        tokenized string
    """
    tokens: list[Token] = []
    parts = string.split()

    for candidate in parts:

        if candidate.isdecimal():
            tokens.append(Token(TokenType.NUMBER, candidate))
            continue

        if candidate.islower():
            tokens.append(Token(TokenType.SYMBOL, candidate))
            continue

        if token := __DEFAULT_TOKENS.get(candidate):
            tokens.append(token)
        else:
            raise RuntimeError(f"Cannot parse '{candidate}'.")

    return tokens


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
