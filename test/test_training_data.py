from calcai.training import SampleData, SampleWriter, from_jsonlines

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
            w.write(item.script, item.result)

    contents = list(from_jsonlines(tmp_path / "output.jsonl"))
    assert data == contents
