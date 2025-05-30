from pathlib import Path

import pytest

from calcai.training import (
    ExpressionGenerator,
    SampleData,
    SampleWriter,
    ScriptBuilder,
    from_jsonlines,
)
from calcai.training.builder import _collect_vars
from calcai.vm import Interpreter

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
        [SampleData(1, "1 + 2", None, 3), SampleData(2, "5 * 2", None, 10)],
        [SampleData(1, "2 * (1 + 2)", "2 * 3", 3), SampleData(2, "2 + 3", None, 5)],
        [SampleData(1, _MULTILINE_1, None, 3), SampleData(2, _MULTILINE_2, None, 10)]
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


@pytest.mark.parametrize("depth", range(1, 4))
def test_gen_expr(depth: int) -> None:
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


@pytest.mark.parametrize("depth", range(1, 3))
@pytest.mark.parametrize("vars", [["x"], ["x", "y"], ["x", "y", "z"]])
def test_gen_expr_with_var(depth: int, vars: list[str]) -> None:
    """Ensure the AST generator works with variables in the expression."""
    vm = Interpreter()
    vm.working_space.store("x", 10)
    vm.working_space.store("y", 20)
    vm.working_space.store("z", 30)

    g = ExpressionGenerator(10)
    for i in range(1000):
        expr = g.generate_expr(depth, i, vars=vars)
        try:
            result = vm.run(expr)
            print(f"Seed {i}: {expr} = {result}")
        except ZeroDivisionError:
            print(f"Seed {i}: {expr} = DIV-BY-ZERO")


def test_gen_assign_expr() -> None:
    g = ExpressionGenerator(10)
    norm_expr = g.generate_expr(3, 1)
    assign_expr = g.generate_expr(3, 1, assign_to="x")
    assert assign_expr == f"x = {norm_expr}"


@pytest.mark.parametrize(
    "expr,vars",
    [
        ("x + y", set(["x", "y"])),
        ("1 + x", set(["x"])),
        ("(1 + (x + 2) + y) + z", set(["x", "y", "z"])),
        ("2 * x ^ 2 + x + 4", set(["x"])),
    ],
)
def test_var_name_collection(expr: str, vars: set[str]) -> None:
    vm = Interpreter()
    root = list(vm.parse(expr))[0]
    assert _collect_vars(root) == vars


@pytest.mark.parametrize("vars", [[], ["x"], ["x", "y"], ["x", "y", "z"]])
@pytest.mark.timeout(1)
def test_script_builder(vars: list[str]) -> None:
    """Script builder generates valid scripts."""
    g = ExpressionGenerator(10)
    builder = ScriptBuilder(g)
    builder.set_variables(vars)
    builder.show_steps(len(vars) == 0)

    for i, output in enumerate(builder.generate_scripts(100)):
        print(f"[{i}::{output.seed}]")
        print(output.script)
        if output.steps is not None:
            print("-")
            print(output.steps)
        print(f"=> {output.result}")
        print("--")
        assert output.seed >= i


@pytest.mark.timeout(1)
def test_error_when_showing_steps_with_vars() -> None:
    """Ensure that using variables with solution steps is (currently) disabled."""
    g = ExpressionGenerator(10)
    builder = ScriptBuilder(g)
    builder.set_variables(["x", "y"])
    builder.show_steps(True)

    with pytest.raises(NotImplementedError):
        next(builder.generate_scripts(1))
