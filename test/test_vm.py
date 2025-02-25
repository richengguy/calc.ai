from calcai.vm import Token, TokenType, tokenize

import pytest


def test_tokenize_empty_string() -> None:
    assert tokenize("") == []


def test_exception_on_invalid_token() -> None:
    with pytest.raises(RuntimeError) as exc:
        tokenize("!")

    assert exc.value.args[0] == "Could not resolve character '!'."


@pytest.mark.parametrize(
    ["input", "tokens"],
    [
        (
            "1 + 2",
            [
                Token(TokenType.NUMBER, "1"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.ADD, "+"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.NUMBER, "2"),
            ],
        ),
        (
            "1 + 2 + 3",
            [
                Token(TokenType.NUMBER, "1"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.ADD, "+"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.NUMBER, "2"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.ADD, "+"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.NUMBER, "3"),
            ],
        ),
        (
            "x = 5 * 3",
            [
                Token(TokenType.SYMBOL, "x"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.EQUALS, "="),
                Token(TokenType.SPACE, " "),
                Token(TokenType.NUMBER, "5"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.MULTIPLY, "*"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.NUMBER, "3"),
            ],
        ),
        (
            "y = (x - 4) / (3 ^ 2)",
            [
                Token(TokenType.SYMBOL, "y"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.EQUALS, "="),
                Token(TokenType.SPACE, " "),
                Token(TokenType.OPEN_BRACKET, "("),
                Token(TokenType.SYMBOL, "x"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.SUBTRACT, "-"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.NUMBER, "4"),
                Token(TokenType.CLOSE_BRACKET, ")"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.DIVIDE, "/"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.OPEN_BRACKET, "("),
                Token(TokenType.NUMBER, "3"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.POWER, "^"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.NUMBER, "2"),
                Token(TokenType.CLOSE_BRACKET, ")"),
            ],
        ),
    ],
)
def test_tokenize(input: str, tokens: list[Token]) -> None:
    """Test tokenization."""
    print(tokenize(input))
    print(tokens)
    assert tokenize(input) == tokens
