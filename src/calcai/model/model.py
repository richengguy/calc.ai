from pathlib import Path
from typing import Iterator

import torch
from torch import Tensor

from .layers import SimpleDecoderTransformer
from .tokenizer import ControlToken, Tokenizer


def create_query(expr: str, *, answer: int | None = None) -> str:
    """Construct a query string.

    Parameters
    ----------
    expr : str
        an arithmetic expression
    answer : int, optional
        if provided, also include the final answer

    Returns
    -------
    str
        full query string
    """
    query = f"{ControlToken.EXPR_START}{expr}{ControlToken.EXPR_STOP}"
    if answer is None:
        return f"{query}{ControlToken.RESULT_START}"
    else:
        return f"{query}{ControlToken.RESULT_START}{answer}{ControlToken.RESULT_STOP}"


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

    @property
    def max_context_size(self) -> int:
        """Maximum context window size."""
        return self._max_context

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

    def training_step(self, input: str, *, init: bool = False) -> Tensor:
        """Perform a single training iteration.

        Parameters
        ----------
        input : str
            input string
        init : bool
            if ``True`` then this resets the model's context window to indicate
            the start of a new training sequence

        Returns
        -------
        Tensor
            the model's next predicted token

        Raises
        ------
        RuntimeError
            if the maximum allowable context window size is exceeded
        """
        if init:
            self._context = list(self._tokenizer.to_tokens(input))
        else:
            self._context.extend(self._tokenizer.to_tokens(input))

        if len(self._context) > self._max_context:
            raise RuntimeError("Exceeded the maximum allowed context size.")

        if not self._model.training:
            self._model.train()

        tokens = Tensor(self._context)
        return self._model(tokens[torch.newaxis, :])

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
