import math
from collections import OrderedDict

import torch
import torch.nn.functional as F
from torch import Tensor
from torch.nn import LayerNorm, Linear, Module, ReLU, Sequential
from torch.nn.init import kaiming_uniform_


class TokenEmbedding(Module):
    """Transforms tokens from a one-hot encoding into some embedding space."""

    def __init__(self, vocab_size: int, num_dim: int) -> None:
        """
        Parameters
        ----------
        vocab_size : int
            the total number of tokens, used to control the size of input vector
        num_dim : int
            the dimensionality of the embedding space
        """
        super().__init__()
        if vocab_size < 1:
            raise ValueError("There must be at least one token.")
        if num_dim >= vocab_size:
            raise ValueError(
                "The embedding dimension cannot be larger than the vocabulary size."
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
        projected: Tensor = self._linear(one_hot)
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
        super().__init__()
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
                f"The last dimension in the input tensor was {x.shape[2]}, expected {self._num_dim}."  # noqa: E501
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


class MaskedAttentionHead(Module):
    """A masked "Attention is all you need" attention head.  That's it."""

    def __init__(
        self, num_dim: int, d_k: int | None = None, d_v: int | None = None
    ) -> None:
        """
        Parameters
        ----------
        num_dim : int
            the dimensionality of the token embedding space
        d_k : int, optional
            the number of columns (dimensions) for the "key" and "query"
            projection matrices; uses `num_dim` if not provided
        d_v : int, optional
            the number of columns (dimensions) for the "value" matrix; uses
            `num_dim` if not provided
        """
        super().__init__()
        if num_dim < 1:
            raise ValueError("Number of dimensions is less than 1")

        d_k = num_dim if d_k is None else d_k
        d_v = num_dim if d_v is None else d_v

        if d_k < 1:
            raise ValueError(
                "Number of columns in the query/key matrix are less than 1"
            )
        if d_v < 1:
            raise ValueError("Number of columns in the value matrix are less than 1")

        self._key = Linear(num_dim, d_k, bias=False)
        self._query = Linear(num_dim, d_k, bias=False)
        self._value = Linear(num_dim, d_v, bias=False)
        self._scale = math.sqrt(d_k)

    def forward(self, x: Tensor) -> tuple[Tensor, Tensor]:
        """Apply the masked attention.

        Parameters
        ----------
        x : Tensor
            input tensor shaped `(B, N_tokens, N_dim)`

        Returns
        -------
        attention : Tensor
            the "attention" tensor, the same shape as the input
        similarity : Tensor
            a `(B, N_tokens, N_tokens)` similarity or "interest" matrix returned
            after computing a softmax
        """
        if x.ndim != 3:
            raise ValueError("Expected input tensor to be (B, N_tokens, N_dim).")

        key: Tensor = self._key(x)
        query: Tensor = self._query(x)
        value: Tensor = self._value(x)

        distances = (query @ key.mT) / self._scale
        infs = torch.full_like(distances, float("-inf"))
        masked = distances + torch.triu(infs, 1)
        similarity = F.softmax(masked, 2)

        attention = similarity @ value
        print(f"=> {attention.shape}")

        return attention, similarity


class TransformerLayer(Module):
    """A single transformer layer.

    This is a combination of a masked attention head, fully-connected network,
    and normalization layers.  This is the same configuration as described in
    "Improving Language Understanding by Generative Pre-Training" by Radford
    et al.
    """

    def __init__(
        self,
        num_dim: int,
        *,
        attention_heads: int = 2,
        d_k: int | None = None,
        d_v: int | None = None,
        d_ff: int | None = None,
    ) -> None:
        """
        Parameters
        ----------
        num_dim : int
            the dimensionality of the token embedding space
        attention_heads : int
            the number of parallel attention heads; default is '2'
        d_k : int, optional
            the number of columns (dimensions) for the "key" and "query"
            projection matrices in the attention head; uses `num_dim` if not
            provided
        d_v : int, optional
            the number of columns (dimensions) for the "value" projection
            matrix in the attention head; uses `num_dim` if not provided
        d_ff : int, optional
            the size of the hidden layer in the fully-connected network that
            follows the attention head; uses `4 * num-dim` if not provided
        """
        super().__init__()
        if num_dim < 1:
            raise ValueError("The embedding space dimension must be greater than 0.")

        d_k = num_dim if d_k is None else d_k
        d_v = num_dim if d_v is None else d_v
        d_ff = 4 * num_dim if d_ff is None else d_ff

        if attention_heads < 1:
            raise ValueError("Need at least one attention head.")

        if attention_heads == 1 and d_v != num_dim:
            raise ValueError(
                "'num_dim' must equal 'd_v' when there is one attention head."
            )

        if d_ff < 1:
            raise ValueError("The value of d_ff must be greater than zero.")

        self._attention = list(
            MaskedAttentionHead(num_dim, d_k, d_v) for _ in range(attention_heads)
        )
        self._merge = Linear(attention_heads * d_v, d_v)
        self._post_attention_layer_norm = LayerNorm(d_v)
        # fmt: off
        self._fully_connected = Sequential(
            Linear(d_v, d_ff),
            ReLU(),
            Linear(d_ff, d_v)
        )
        # fmt: on
        self._post_fcn_layer_norm = LayerNorm(d_v)

    def forward(self, x: Tensor) -> Tensor:
        """Apply the transformer layer.

        Parameters
        ----------
        x : Tensor
            input tensor shaped `(B, N_tokens, N_dim)`

        Returns
        -------
        Tensor
            the transformer output, same shape as the input
        """
        print(f"-- {x.shape}")
        attention_heads = list(head(x)[0] for head in self._attention)
        concat = torch.concat(attention_heads, dim=2)
        print(f"-- {[a.shape for a in attention_heads]}")
        print(f"-- {concat.shape}")
        attention = self._merge(concat)

        # Do all of the post-attention processing.  This includes the residual
        # connections (the additions).
        attention_normalized: Tensor = self._post_attention_layer_norm(attention + x)
        fcn: Tensor = self._fully_connected(attention_normalized)
        fcn_normalized: Tensor = self._post_attention_layer_norm(
            fcn + attention_normalized
        )

        return fcn_normalized


class SimpleDecoderTransformer(Module):
    """A decoder-only transformer model.

    It's a simplified decoder-only transformer architecture that will predict
    the next token from the set of provided tokens.  While the model outputs
    logits instead of probabilities, the highest valued element still
    corresponds to the most likely token.
    """

    def __init__(
        self,
        vocab_size: int,
        num_dim: int,
        *,
        num_layers: int = 4,
        d_k: int | None = None,
        d_v: int | None = None,
        d_ff: int | None = None,
    ) -> None:
        """
        Parameters
        ----------
        vocab_size : int
            the number of tokens in the vocabulary that the tokenizer recognizes
        num_dim : int
            the desired dimensionality of the token embedding space; this should
            be smaller than the vocabulary size
        num_layers : int
            the number of transformer layers; defaults to '4'
        d_k : int, optional
            the number of columns (dimensions) for the "key" and "query"
            projection matrices in the attention heads; uses `num_dim` if not
            provided
        d_v : int, optional
            the number of columns (dimensions) for the "value" projection
            matrix in the attention heads; uses `num_dim` if not provided
        d_ff : int, optional
            the size of the hidden layer in the fully-connected network that
            follows the attention heads; uses `4 * num-dim` if not provided
        """
        super().__init__()

        generation_layers: list[tuple[str, Module]] = [
            ("embedding", TokenEmbedding(vocab_size, num_dim)),
            ("position-encoding", PositionEncoding(num_dim)),
        ]

        for i in range(num_layers):
            generation_layers.append(
                (
                    f"transformer{i}",
                    TransformerLayer(num_dim, d_k=d_k, d_v=d_v, d_ff=d_ff),
                )
            )

        generation_layers.append(("decoding", Linear(num_dim, vocab_size)))

        prediction_layers = [
            ("transformer", TransformerLayer(vocab_size, attention_heads=1)),
            ("projection", Linear(vocab_size, 1)),
        ]

        self._generator = Sequential(OrderedDict(generation_layers))
        self._predictor = Sequential(OrderedDict(prediction_layers))

    def forward(self, x: Tensor) -> tuple[Tensor, Tensor]:
        """Compute the likelihood of the next token.

        Parameters
        ----------
        x : Tensor
            input tensor shaped `(B, N_tokens)`; this is a list of token indices

        Returns
        -------
        logits : Tensor
            a tensor of *logits* shaped `(B, vocab_size)`; to get
            probabilities take the `exp()` of this tensor
        result : Tensor
            a batch-sized tensor, i.e., `(B,)`, containing the predicted
            numerical result of the input token sequence
        """
        output: Tensor = self._generator(x)
        result: Tensor = self._predictor(output)
        logits = F.log_softmax(output[:, -1, :], 1)
        return logits, result[:, -1, 0]
