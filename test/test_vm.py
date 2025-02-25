from calcai.vm import Token, TokenType, tokenize

import pytest


@pytest.mark.parametrize(
    ["input", "tokens"],
    [
        (
            "1 + 2",
            [
                Token(TokenType.NUMBER, "1"),
                Token(TokenType.ADD, "+"),
                Token(TokenType.NUMBER, "2"),
            ],
        ),
        (
            "x = 5 * 3",
            [
                Token(TokenType.SYMBOL, "x"),
                Token(TokenType.EQUALS, "="),
                Token(TokenType.NUMBER, "5"),
                Token(TokenType.MULTIPLY, "*"),
                Token(TokenType.NUMBER, "3"),
            ],
        ),
        (
            "y = (x - 4) / (3 ^ 2)",
            [
                Token(TokenType.SYMBOL, "y"),
                Token(TokenType.EQUALS, "="),
                Token(TokenType.OPEN_BRACKET, "("),
                Token(TokenType.SYMBOL, "x"),
                Token(TokenType.SUBTRACT, "-"),
                Token(TokenType.NUMBER, "4"),
                Token(TokenType.CLOSE_BRACKET, ")"),
                Token(TokenType.DIVIDE, "/"),
                Token(TokenType.OPEN_BRACKET, "("),
                Token(TokenType.NUMBER, "3"),
                Token(TokenType.POWER, "^"),
                Token(TokenType.CLOSE_BRACKET, ")"),
            ],
        ),
    ],
)
def test_tokenize(input: str, tokens: list[Token]) -> None:
    """Test tokenization."""
    assert tokenize(input) == tokens
