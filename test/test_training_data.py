from calcai.training import (
    SampleData,
    SampleWriter,
    from_jsonlines,
    ExpressionGenerator,
)
from calcai.vm import Interpreter

from pathlib import Path

import pytest

_MULTILINE_1 = """
x = 1
y = 2
x + y
"""

_MULTILINE_2 = """
u = 5
v = 2
u * v
"""


# fmt:off
@pytest.mark.parametrize(
    "data",
    [
        [SampleData("1 + 2", 3), SampleData("5 * 2", 10)],
        [SampleData(_MULTILINE_1, 3), SampleData(_MULTILINE_2, 10)]
    ]
)
# fmt: on
def test_serialize_to_jsonlines(data: list[SampleData], tmp_path: Path) -> None:
    """Test serializing data to a JSON lines file."""
    with SampleWriter(tmp_path / "output.jsonl") as w:
        for item in data:
            w.write(item)

    contents = list(from_jsonlines(tmp_path / "output.jsonl"))
    assert data == contents


@pytest.mark.parametrize("depth", range(1, 3))
def test_ast_validity(depth: int) -> None:
    """Ensure the AST generator is generating expression the VM can parse."""
    g = ExpressionGenerator(10)
    vm = Interpreter()

    # Run through a large number of seeds and see what the VM does. Divisions by
    # zero *are* possible with arbitrary expressions so hitting a divide-by-zero
    # isn't an error.
    for i in range(1000):
        expr = g.generate_expr(depth, i)

        try:
            result = vm.run(expr)
            print(f"Seed {i}: {expr} = {result}")
        except ZeroDivisionError:
            print(f"Seed {i}: {expr} = DIV-BY-ZERO")
