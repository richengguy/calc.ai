import pytest

from calcai.model.tokenizer import ControlToken, Tokenizer, Query


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
    with pytest.raises(ValueError, match=bad_token):
        list(t.to_tokens(input))


@pytest.mark.parametrize(
    "expr,result,expected,show_result",
    [
        ("1 + 2", None, "{expr=}1 + 2{=expr}", False),
        ("1 + 2", 3, "{expr=}1 + 2{=expr}{result=}3{=result}", True),
        ("3 / 0", None, "{expr=}3 / 0{=expr}{result=}{null}{=result}", True)
    ]
)
def test_create_query(expr: str, result: int | None, expected: str, show_result: bool) -> None:
    query = Query(expr, result=result)
    query.show_result(show_result)
    assert str(query) == expected


@pytest.mark.parametrize(
    "query,expr,result",
    [
        ("{expr=}1 + 2{=expr}", "1 + 2", None),
        ("{expr=}1 + 2{=expr}{result=}3{=result}", "1 + 2", 3),
        ("{expr=}3 / 0{=expr}{result=}{null}{=result}", "3 / 0", None)
    ]
)
def test_parse_valid_queries(query: str, expr: str, result: int | None) -> None:
    tokenizer = Tokenizer()
    parsed = Query.parse(query, tokenizer)
    assert parsed.expr == expr
    assert parsed.result == result


@pytest.mark.parametrize(
    "query",
    [
        "{expr=}1 + 2",
        "1 + 2",
        "{expr=}1 + 2{=expr}3{=result}",
        "{expr=}1 + 2{=expr}{result=}3",
        "{expr=}1 + 2{=expr}{result=}abc{=result}",
        "{expr=}1 + 2{=expr}{expr=}{result=}3{=result}",
    ]
)
def test_parse_invalid_queries(query: str) -> None:
    tokenizer = Tokenizer()
    with pytest.raises(ValueError):
        Query.parse(query, tokenizer)
