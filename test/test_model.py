from pathlib import Path

import pytest
from torch.nn import Linear
from torch.testing import assert_close

from calcai.model import CalculatorLanguageModel


@pytest.mark.parametrize("embedding_dimension", [8, 16, 32])
@pytest.mark.parametrize("layers", [3, 4, 5])
def test_serialization(embedding_dimension: int, layers: int, tmp_path: Path) -> None:
    """Ensure that a model can be serialized and deserialized."""
    model_file = tmp_path / "model.pt"

    model = CalculatorLanguageModel(
        embedding_dimensions=embedding_dimension, layers=layers, max_context=128
    )
    model.save(model_file)

    deserialized = CalculatorLanguageModel.load(model_file)
    assert deserialized.max_context_size == 128
    for expected, actual in zip(
        model.pytorch_model.parameters(), deserialized.pytorch_model.parameters()
    ):
        assert_close(expected, actual)


def test_bad_serialization() -> None:
    """Error raised when trying to load an invalid model type."""
    with pytest.raises(ValueError):
        CalculatorLanguageModel(model=Linear(10, 5))
