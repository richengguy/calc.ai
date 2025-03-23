import pytest
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
