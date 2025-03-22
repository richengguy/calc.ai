from torch import Tensor
from torch.nn import functional as F
from torch.nn import Module, Linear, ReLU
from torch.nn.init import kaiming_uniform_


class TokenEmbedding(Module):
    """Transforms tokens from a one-hot encoding into some embedding space."""
    def __init__(self, num_tokens: int, num_dim: int = 16) -> None:
        """
        Parameters
        ----------
        num_tokens : int
            the total number of tokens, used to control the size of input vector
        num_dim : int
            the dimensionality of the embedding space; defaults to 16
        """
        super().__init__()
        if num_tokens < 1:
            raise ValueError("There must be at least one token.")
        if num_dim < num_tokens:
            raise ValueError("The embedding dimension cannot be smaller than the number of tokens.")

        self._num_tokens = num_tokens

        self._linear = Linear(num_tokens, num_dim)
        self._relu = ReLU()
        kaiming_uniform_(self._linear.weight, nonlinearity="relu")

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
        one_hot = F.one_hot(tokens, self._num_tokens)
        projected = self._linear(one_hot)
        activation = self._relu(projected)
        return activation
