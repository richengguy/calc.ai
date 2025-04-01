import math

import pytest
import torch
import torch.nn.functional as F
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


@pytest.mark.parametrize("batch", (1, 2, 3))
@pytest.mark.parametrize("num_tokens", (2, 3, 4, 5))
@pytest.mark.parametrize("num_dim", (4, 6, 8, 10))
def test_position_encoding(batch: int, num_tokens: int, num_dim: int) -> None:
    """Verify the position encoding is applied correctly."""
    input = torch.zeros((batch, num_tokens, num_dim))
    encoding = layers.PositionEncoding(num_dim)
    output = encoding.forward(input)
    assert output.shape == input.shape


@pytest.mark.parametrize("batch", (1, 2, 3))
@pytest.mark.parametrize("num_tokens", (2, 3, 4, 5))
@pytest.mark.parametrize("num_dim", (4, 6, 8, 10))
def test_attention_layer(batch: int, num_tokens: int, num_dim: int) -> None:
    """Verify the attention layer is being calculated correctly."""
    input = torch.zeros((batch, num_tokens, num_dim))
    for i in range(num_tokens):
        input[:, i, (i % num_dim)] = 1

    # This computes what the similarity matrix the attention layer computes
    # should look like.  This is actually not too hard to compute directly if a
    # few assumptions are made.
    #
    # First, assume that the transformation matrices that convert the set of
    # tokens, X, into the Q, K, and V matrices are all be identity so that
    # X = Q = K = V. Second, consider that the full attention is computed as
    #
    #       A = softmax(QK^T/sqrt(Dk))V
    #
    # where 'Dk' is the number of columns in 'K'.  If the first assumption is
    # true then this can be rewritten as
    #
    #       A = softmax(XX^T/sqrt(Dk))X
    #
    # This means the expected similarity matrix is
    #
    #       S = softmax(XX^T/sqrt(Dk))
    #
    # Calculating this is straightforward.  The remaining work is to then just
    # to compare the results between the attention layer and the expected
    # output.

    dotprod = (input @ input.mT) / math.sqrt(num_dim)
    dotprod = dotprod + torch.triu(torch.full_like(dotprod, float("-inf")), 1)
    expected_similarity = F.softmax(dotprod, -1)

    attention = layers.MaskedAttentionHead(num_dim)

    with torch.no_grad():
        attention._key.weight.copy_(torch.eye(num_dim))
        attention._query.weight.copy_(torch.eye(num_dim))
        attention._value.weight.copy_(torch.eye(num_dim))

    output, similarity = attention.forward(input)
    torch.testing.assert_close(similarity, expected_similarity)
    torch.testing.assert_close(expected_similarity @ input, output)


@pytest.mark.parametrize("batch", (1, 2, 3))
@pytest.mark.parametrize("num_tokens", (2, 3, 4, 5))
@pytest.mark.parametrize("num_dim", (4, 6, 8, 10))
def test_transformer_layer(batch: int, num_tokens, num_dim: int) -> None:
    """Verify the transformer input/output are correctly shaped."""
    input = torch.zeros((batch, num_tokens, num_dim))
    transform = layers.TransformerLayer(num_dim)
    output = transform.forward(input)
    assert output.shape == input.shape


@pytest.mark.parametrize("batch", (1, 2, 3))
@pytest.mark.parametrize("vocab_size", (15, 20, 30))
@pytest.mark.parametrize("num_tokens", (2, 3, 5, 10, 20))
@pytest.mark.parametrize("num_dim", (4, 6, 8, 10))
def test_full_language_model(
    batch: int, vocab_size: int, num_tokens: int, num_dim: int
) -> None:
    """Verify the full language model is wired up correctly."""
    input = Tensor([i % vocab_size for i in range(num_tokens)])
    input = input.repeat((batch, 1))
    model = layers.SimpleDecoderTransformer(vocab_size, num_dim)
    output = model.forward(input)
    assert output.shape == (batch, 1, vocab_size)


def test_error_on_odd_embedding_size_for_position_encoding() -> None:
    """Raise an exception if the embedding space has an odd number of dimensions."""
    with pytest.raises(ValueError):
        layers.PositionEncoding(3)
