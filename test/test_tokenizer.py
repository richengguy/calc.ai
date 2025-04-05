import pytest

from calcai.model import create_query
from calcai.model.tokenizer import ControlToken, Tokenizer


@pytest.mark.parametrize("token", list(ControlToken))
def test_control_tokens(token: ControlToken) -> None:
    """Verify control tokens are handled correctly."""
    t = Tokenizer()
    token_id = next(t.to_tokens(token.value))

    assert token.value in t.forward_map
    assert t.reverse_map[token_id] == token.value


# fmt: off
@pytest.mark.parametrize(
    "input",
    [
        "{expr=}1 + 2 * 3{=expr}",
        "3 * (1 + 4)",
        "x+y{result=}10{=result}",
    ]
)
# fmt: on
def test_tokenizer_roundtrip(input: str) -> None:
    """Can roundtrip between a string and a token list."""
    t = Tokenizer()
    tokens = list(t.to_tokens(input))
    output = "".join(t.from_tokens(tokens))
    assert input == output


@pytest.mark.parametrize(
    "input,bad_token",
    [
        ("{{expr=}", "{{expr=}"),
        ("1+2{=expr", "{=expr"),
        ("abc+{=result}}", "}"),
        ("{unknown=}{=unknown}", "{unknown=}"),
    ],
)
def test_tokenizer_error_handling(input: str, bad_token: str) -> None:
    """Can correctly report bad token syntax."""
    t = Tokenizer()
    with pytest.raises(RuntimeError, match=bad_token):
        list(t.to_tokens(input))


def test_create_query() -> None:
    assert create_query("1 + 2") == "{expr=}1 + 2{=expr}{result=}"
    assert create_query("1 + 2", answer=3) == "{expr=}1 + 2{=expr}{result=}3{=result}"
