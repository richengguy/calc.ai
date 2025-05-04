import pytest

from calcai.model.tokenizer import ControlToken, Query, Tokenizer


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
    "expr,result,steps,expected,show_result,show_steps",
    [
        ("1 + 2", None, None, "{expr=}1 + 2{=expr}", False, False),
        ("1 + 2", 3, None, "{expr=}1 + 2{=expr}{result=}3{=result}", True, False),
        (
            "1 + 2 * 2",
            5,
            "1 + 4",
            "{expr=}1 + 2 * 2{=expr}{steps=}1 + 4{=steps}{result=}5{=result}",
            True,
            True,
        ),
        (
            "1 + 2 * 2",
            5,
            "1 + 4",
            "{expr=}1 + 2 * 2{=expr}{result=}5{=result}",
            True,
            False,
        ),
        (
            "1 + 2 * 2",
            5,
            "1 + 4",
            "{expr=}1 + 2 * 2{=expr}{steps=}1 + 4{=steps}",
            False,
            True,
        ),
        ("1 + 2 * 2", 5, "1 + 4", "{expr=}1 + 2 * 2{=expr}", False, False),
        (
            "3 / 0",
            None,
            None,
            "{expr=}3 / 0{=expr}{result=}{null}{=result}",
            True,
            False,
        ),
    ],
)
def test_create_query(
    expr: str,
    result: int | None,
    steps: str | None,
    expected: str,
    show_result: bool,
    show_steps: bool,
) -> None:
    query = Query(expr, steps=steps, result=result)
    query.show_result(show_result)
    query.show_steps(show_steps)
    assert str(query) == expected


@pytest.mark.parametrize(
    "query,expr,result",
    [
        ("{expr=}1 + 2{=expr}", "1 + 2", None),
        ("{expr=}1 + 2{=expr}{result=}3{=result}", "1 + 2", 3),
        ("{expr=}3 / 0{=expr}{result=}{null}{=result}", "3 / 0", None),
        (
            "{expr=}-(10 * 42){=expr}{steps=}-(420){=steps}{result=}-420{=result}",
            "-(10 * 42)",
            -420,
        ),
        (
            "{expr=}0 - 9 * -30{=expr}{steps=}0 - 9 * -30\n0 - -270{=steps}{result=}270{=result}",
            "0 - 9 * -30",
            270,
        ),
    ],
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
        "{expr=}1 + 2{=expr}{expr=}{result=}3{=result}{solution=}abc{=solution}",
    ],
)
def test_parse_invalid_queries(query: str) -> None:
    tokenizer = Tokenizer()
    with pytest.raises(ValueError):
        Query.parse(query, tokenizer)
