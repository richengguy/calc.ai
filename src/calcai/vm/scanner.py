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

    SPACE = auto()
    """Token represents whitespace, either a ' ' or a tab."""


@dataclass(frozen=True)
class Token:
    """Represents a single token."""

    type: TokenType
    """The token's type."""

    value: str
    """The token's value."""


__DEFAULT_TOKENS: dict[str, Token] = {
    "+": Token(TokenType.ADD, "+"),
    "-": Token(TokenType.SUBTRACT, "-"),
    "*": Token(TokenType.MULTIPLY, "*"),
    "/": Token(TokenType.DIVIDE, "/"),
    "^": Token(TokenType.POWER, "^"),
    "(": Token(TokenType.OPEN_BRACKET, "("),
    ")": Token(TokenType.CLOSE_BRACKET, ")"),
    "=": Token(TokenType.EQUALS, "="),
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

    string = string.lower()
    buffer = ""

    def resolve(ch: str) -> TokenType:
        if ch.isspace():
            return TokenType.SPACE
        elif ch.isdecimal():
            return TokenType.NUMBER
        elif ch.islower():
            return TokenType.SYMBOL
        elif token := __DEFAULT_TOKENS.get(ch):
            return token.type

        raise RuntimeError(f"Could not resolve character '{ch}'.")

    for i in range(len(string)):
        curr_ch = string[i]
        next_ch = string[i + 1] if i < len(string) - 1 else curr_ch

        # It's obvious what token this is.  Just use it directly and reset the
        # buffer.
        if token := __DEFAULT_TOKENS.get(curr_ch):
            tokens.append(token)
            continue

        # Determine the types of the current and *next* characters.
        curr_type = resolve(curr_ch)
        next_type = resolve(next_ch)

        # Now emit a token, either when reaching the end of a string or when the
        # type changes.
        buffer += curr_ch
        if curr_type == next_type:
            if i == len(string) - 1:
                tokens.append(Token(curr_type, buffer))
        else:
            tokens.append(Token(curr_type, buffer))
            buffer = ""

    return tokens
