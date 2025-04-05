from pathlib import Path
from typing import Iterator

import torch
from torch import Tensor

from .layers import SimpleDecoderTransformer
from .tokenizer import ControlToken, Tokenizer


class CalculatorLanguageModel:
    """A simple transformer for computing arithmetic expressions.

    The Calculator Language Model (CLM) will accept a string, something like
    `1 + 2`, and, in theory, generate `3`.
    """

    def __init__(
        self, *, embedding_dimensions: int = 16, max_context: int = 256
    ) -> None:
        """
        Parameters
        ----------
        embedding_dimensions : int
            size of the token embedding space; defaults to 16
        max_context : int
            maximum number of tokens the model can work with; defaults to 256
        """
        self._tokenizer = Tokenizer()
        self._model = SimpleDecoderTransformer(
            self._tokenizer.num_tokens, embedding_dimensions
        )
        self._max_context = max_context
        self._context: list[int] = []

    def predict(self, query: str) -> Iterator[str]:
        """Predict tokens, given some input.

        Parameters
        ----------
        query : str
            input query string

        Yields
        ------
        str
            the set of tokens produced by the model; this will go up to a
            terminal token or the context window is exhausted
        """
        context = torch.zeros((1, self._max_context))
        for i, token in enumerate(self._tokenizer.to_tokens(query)):
            context[0, i] = token

        start_ind = i
        self._model.eval()
        with torch.no_grad():
            for i in range(start_ind, self._max_context):
                logits: Tensor = self._model(context[0, 0:i])

                # Use the highest probability token as the result.
                token = int(logits[0, 0, :].argmax().item())
                yield self._tokenizer.reverse_map[token]

                # Stop processing if we see a "result end" token.
                if token == ControlToken.RESULT_STOP:
                    break

    def reset(self) -> None:
        """Resets the model's internal state."""
        self._context.clear()

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
