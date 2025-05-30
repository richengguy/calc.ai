import pytest

from calcai.vm import Interpreter, build_ast, tokenize
from calcai.vm.ast import ExpressionType
from calcai.vm.runtime import WorkingSpace
from calcai.vm.scanner import Token, TokenType


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
        (
            "abc = 123",
            [
                Token(TokenType.SYMBOL, "abc"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.EQUALS, "="),
                Token(TokenType.SPACE, " "),
                Token(TokenType.NUMBER, "123"),
            ],
        ),
        (
            "a1 = 5",
            [
                Token(TokenType.SYMBOL, "a1"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.EQUALS, "="),
                Token(TokenType.SPACE, " "),
                Token(TokenType.NUMBER, "5"),
            ],
        ),
        (
            "y1 = (x1 - x2) / (3 + 2)",
            [
                Token(TokenType.SYMBOL, "y1"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.EQUALS, "="),
                Token(TokenType.SPACE, " "),
                Token(TokenType.OPEN_BRACKET, "("),
                Token(TokenType.SYMBOL, "x1"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.SUBTRACT, "-"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.SYMBOL, "x2"),
                Token(TokenType.CLOSE_BRACKET, ")"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.DIVIDE, "/"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.OPEN_BRACKET, "("),
                Token(TokenType.NUMBER, "3"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.ADD, "+"),
                Token(TokenType.SPACE, " "),
                Token(TokenType.NUMBER, "2"),
                Token(TokenType.CLOSE_BRACKET, ")"),
            ],
        ),
    ],
)
def test_tokenize(input: str, tokens: list[Token]) -> None:
    """Test tokenization."""
    assert tokenize(input) == tokens


# fmt: off
@pytest.mark.parametrize(
    ["input", "expr_type", "value"],
    [
        ("123", ExpressionType.NUMBER, 123),
        ("abc", ExpressionType.VARIABLE, 456),
    ],
)
# fmt: on
def test_single_token_ast(input: str, expr_type: ExpressionType, value: int) -> None:
    """Verify a single-token, or terminal, AST is creating correctly."""
    ws = WorkingSpace()
    ws.store("abc", 456)
    expr = build_ast(tokenize(input))
    assert expr.type == ExpressionType.EXPRESSION
    assert expr.input.type == expr_type
    assert expr.evaluate(ws) == value


# fmt: off
@pytest.mark.parametrize(
    ["var", "eqn", "value"],
    [
        ("x", "123", 123),
        ("y", "1 + 2", 3),
        ("z", "-4 + 2 * (3 + 2)", 6),
    ],
)
# fmt: on
def test_assignment_ast(var: str, eqn: str, value: int) -> None:
    """Check to see if assignment works as expected."""
    ws = WorkingSpace()
    expr = build_ast(tokenize(f"{var} = {eqn}"))
    assert expr.evaluate(ws) == value
    assert ws.load(var) == value


# fmt: off
@pytest.mark.parametrize(
    ["input", "value"],
    [
        ("(1)", 1),
        ("(((2)))", 2),
        ("(((2))) + 1", 3),
        ("3 * 2 + 3", 9),
        ("3 * (2 + 3)", 15),
        ("(5 + 5) / 2", 5),
    ]
)
# fmt: on
def test_brackets_ast(input: str, value: int) -> None:
    """Check to see if grouped expressions are working."""
    ws = WorkingSpace()
    expr = build_ast(tokenize(input))
    assert expr.evaluate(ws) == value


# fmt: off
@pytest.mark.parametrize(
    "input",
    [
        "1",
        "1 + 2",
        "2 * 3 + 1",
        "5 ^ (1 + 2)",
        "x + 5",
        "x = (1 + 1) / 2",
    ]
)
# fmt: on
def test_print_ast(input: str) -> None:
    """Check if the AST can be round-tripped by printing it."""
    expr = build_ast(tokenize(input))
    assert expr.print() == input


def test_oneline_script() -> None:
    """Have the interpreter parse a single-line script."""
    vm = Interpreter()
    assert vm.run("1 + 2 + 3") == 6


def test_multiline_script() -> None:
    """Have the interpreter parse a multi-line script."""
    script = """
    x = 1
    y = 5*3
    x + y
    """
    vm = Interpreter()
    assert vm.run(script) == 16
    assert vm.working_space.load("x") == 1
    assert vm.working_space.load("y") == 15


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("1", []),
        ("1 + 2", ["3"]),
        ("(1)", ["1"]),
        ("-(1)", ["-1"]),
        (
            "(1 + 2) * (3 + 4)",
            ["(3) * (3 + 4)", "3 * (3 + 4)", "3 * (7)", "3 * 7", "21"],
        ),
        (
            "(5 * (1 + 2) - 8 * (1)) + 5",
            [
                "(5 * (3) - 8 * (1)) + 5",
                "(5 * 3 - 8 * (1)) + 5",
                "(15 - 8 * (1)) + 5",
                "(15 - 8 * 1) + 5",
                "(15 - 8) + 5",
                "(7) + 5",
                "7 + 5",
                "12",
            ],
        ),
    ],
)
def test_solution_steps(expr: str, expected: list[str]) -> None:
    """Have the interpreter show how to solve an expression."""
    vm = Interpreter()
    steps: list[str] = []
    for step in vm.solution_steps(expr):
        steps.append(step.print())
    print("\n".join(steps))
    assert steps == expected


def test_exception_on_empty_input() -> None:
    with pytest.raises(RuntimeError) as exc:
        vm = Interpreter()
        vm.run("")

    assert str(exc.value) == "There was no result to return!"
