import pytest
import torch
from torch import Tensor

from calcai.model import layers


@pytest.mark.parametrize("vocab_size, num_dim", ([10, 5], [20, 10]))
@pytest.mark.parametrize("num_tokens", (5, 10, 20))
def test_embedding_layer(vocab_size: int, num_tokens: int, num_dim: int) -> None:
    """Verify the embedding layer produces the correct output sizes."""
    input = Tensor([i % vocab_size for i in range(num_tokens)])
    embedding = layers.TokenEmbedding(vocab_size, num_dim)
    output = embedding.forward(input)
    assert output.shape == (num_tokens, num_dim)


@pytest.mark.parametrize("num_tokens", (2, 3, 4, 5))
@pytest.mark.parametrize("num_dim", (4, 6, 8, 10))
def test_position_encoding(num_tokens: int, num_dim: int) -> None:
    """Verify the position encoding is applied correctly."""
    input = torch.zeros((2, num_tokens, num_dim))
    encoding = layers.PositionEncoding(num_dim)
    output = encoding.forward(input)
    assert output.shape == input.shape


def test_error_on_odd_embedding_size_for_position_encoding() -> None:
    """Raise an exception if the embedding space has an odd number of dimensions."""
    with pytest.raises(ValueError):
        layers.PositionEncoding(3)
