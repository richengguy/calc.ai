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

        self._linear = Linear(vocab_size, num_dim)
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
        one_hot = F.one_hot(tokens.long(), self._vocab_size).float()
        projected = self._linear(one_hot)
        return projected
