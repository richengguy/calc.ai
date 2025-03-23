import math

import torch
from torch import Tensor
from torch.nn import Linear, Module
from torch.nn import functional as F
from torch.nn.init import kaiming_uniform_


class TokenEmbedding(Module):
    """Transforms tokens from a one-hot encoding into some embedding space."""

    def __init__(self, vocab_size: int, num_dim: int = 16) -> None:
        """
        Parameters
        ----------
        vocab_size : int
            the total number of tokens, used to control the size of input vector
        num_dim : int
            the dimensionality of the embedding space; defaults to 16
        """
        super().__init__()
        if vocab_size < 1:
            raise ValueError("There must be at least one token.")
        if num_dim >= vocab_size:
            raise ValueError(
                "The embedding dimension cannot be larger than the number of tokens."
            )

        self._vocab_size = vocab_size
        self._num_dim = num_dim

        self._linear = Linear(vocab_size, num_dim)
        kaiming_uniform_(self._linear.weight, nonlinearity="relu")

    @property
    def vocab_size(self) -> int:
        return self._vocab_size

    @property
    def num_dim(self) -> int:
        return self._num_dim

    def forward(self, tokens: Tensor) -> Tensor:
        """Project the token sequence into the embedding space.

        Parameters
        ----------
        tokens : Tensor
            input sequence

        Returns
        -------
        Tensor
            projected tokens
        """
        one_hot = F.one_hot(tokens.long(), self._vocab_size).float()
        projected = self._linear(one_hot)
        return projected


class PositionEncoding(Module):
    """Applies a position encoding to an input tensor.

    This uses the same sine/cosine encoding scheme from the original "Attention
    is all you need" paper.  This creates a unique sinusoid for each token
    position.

    A more detailed explanation on how this position encoding works can be found
    in https://machinelearningmastery.com/a-gentle-introduction-to-positional-encoding-in-transformer-models-part-1/
    """  # noqa: E501

    def __init__(self, num_dim: int, n: float = 10000) -> None:
        """
        Parameters
        ----------
        num_dim : int
            the dimensionality of the embedding space; this must be an even
            number
        n : int
            the scalar value that controls the "base" sinusoid frequency;
            defaults to 10'000 since this is what was used in the original
            paper
        """
        if num_dim % 2 != 0:
            # This isn't strictly necessary but odd-valued embedding spaces make
            # the indexing math a bit messy.
            raise ValueError("Input dimensionality must be an even value.")

        denom_size = math.ceil(num_dim / 2)
        self._denom = torch.pow(n, 2 * torch.arange(0, denom_size) / num_dim)
        self._num_dim = num_dim
        self._n = n

    def forward(self, x: Tensor) -> Tensor:
        """Apply the position encoding.

        Parameters
        ----------
        x : Tensor
            input tensor shaped `(B, N_tokens, N_dim)`

        Returns
        -------
        Tensor
            the tensor with the position encoding applied
        """
        if x.ndim != 3:
            raise RuntimeError("Tensor must only have three dimensions.")

        if x.shape[2] != self._num_dim:
            raise RuntimeError(
                f"The last dimension in the input tensor was {x.shape[-1]}, expected {self._num_dim}."
            )

        num_tokens = x.shape[1]
        size_denom = len(self._denom)

        # This does some resizing so that the indices and denominator vectors
        # are the same size.  This is done using views so no new memory should
        # be allocated
        inds = (
            torch.arange(num_tokens).reshape((num_tokens, 1)).expand((-1, size_denom))
        )
        denom = self._denom.expand((num_tokens, -1))

        # This then computes the odd and even indices of the position vector.
        odd_dim = torch.sin(inds / denom)
        evn_dim = torch.cos(inds / denom)

        encoding = torch.zeros_like(x)
        encoding[:, :, 0::2] = odd_dim
        encoding[:, :, 1::2] = evn_dim

        return x + encoding
