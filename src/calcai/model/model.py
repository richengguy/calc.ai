from .layers import SimpleDecoderTransformer
from .tokenizer import ControlToken, Tokenizer

from torch import Tensor
from pathlib import Path


class CalculatorLanguageModel:
    """A simple transformer for computing arithmetic expressions.

    The Calculator Language Model (CLM) will accept a string, something like
    `1 + 2`, and, in theory, generate `3`.
    """

    def __init__(self, *, embedding_dimensions: int = 16) -> None:
        """
        Parameters
        ----------
        embedding_dimensions : int
            size of the token embedding space; defaults to 16
        """
        self._tokenizer = Tokenizer()
        self._model = SimpleDecoderTransformer(
            self._tokenizer.num_tokens, embedding_dimensions
        )

    def save(self, path: Path) -> None:
        """Save the model.

        Parameters
        ----------
        path : Path
            location where to save the model
        """

    @staticmethod
    def load(self, path: Path) -> "CalculatorLanguageModel":
        """Load a model.

        Parameters
        ----------
        path : Path
            location where the model is saved
        """
        raise NotImplementedError()
