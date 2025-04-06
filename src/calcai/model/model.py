from pathlib import Path
from typing import Iterator

import torch
from torch import Tensor
from torch.nn import Module

from .layers import SimpleDecoderTransformer
from .tokenizer import ControlToken, Tokenizer


def create_query(expr: str) -> str:
    """Construct a query string that is sent into the CLM.

    Parameters
    ----------
    expr : str
        an arithmetic expression script
    answer : int, optional
        if provided, also include the final answer

    Returns
    -------
    str
        full query string
    """
    query = f"{ControlToken.EXPR_START}{expr}{ControlToken.EXPR_STOP}"
    return f"{query}{ControlToken.RESULT_START}"


def create_output_string(expr: str, answer: int | None) -> str:
    """Construct a complete output string.

    This is the complete string that the CLM should produce when it computes an
    answer.

    Parameters
    ----------
    expr : str
        an arithmetic expression
    answer : int or `None`
        the expected result; if the script cannot be computed, e.g., in the
        "divide by zero" case, then this should be `None`

    Returns
    -------
    str
        the output string
    """
    output = create_query(expr)
    answer_str = ControlToken.NULL if answer is None else answer
    return f"{output}{answer_str}{ControlToken.RESULT_STOP}"


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
        self.tokenizer = Tokenizer()
        self._model = SimpleDecoderTransformer(
            self.tokenizer.num_tokens, embedding_dimensions
        )
        self._max_context = max_context
        self._context: list[int] = []

    @property
    def max_context_size(self) -> int:
        """Maximum context window size."""
        return self._max_context

    @property
    def pytorch_model(self) -> Module:
        """The underlying PyTorch model."""
        return self._model

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
        context = torch.zeros((self._max_context,))
        for i, token in enumerate(self.tokenizer.to_tokens(query)):
            context[i] = token

        start_ind = i
        stop_token = self.tokenizer.forward_map[ControlToken.RESULT_STOP]
        self._model.eval()
        with torch.no_grad():
            for i in range(start_ind, self._max_context - 1):
                logits: Tensor = self._model(context[torch.newaxis, 0:i])

                # Use the highest probability token as the result.
                token = int(logits[0, :].argmax().item())
                yield self.tokenizer.reverse_map[token]

                # Stop processing if we see a "result end" token.
                if token == stop_token:
                    break

                context[i + 1] = token

    def inference_step(
        self, input: list[int], *, init: bool = False
    ) -> tuple[Tensor, int]:
        """Perform a single inference step.

        Parameters
        ----------
        input : str
            input string
        init : bool
            if ``True`` then this resets the model's context window to indicate
            the start of a new training sequence

        Returns
        -------
        logit : Tensor
            the logit for model's next predicted token
        index : int
            the index of the largest logit (highest probability token)

        Raises
        ------
        RuntimeError
            if the maximum allowable context window size is exceeded
        """
        if init:
            self._context = list()

        self._context.extend(input)

        if len(self._context) > self._max_context:
            raise RuntimeError("Exceeded the maximum allowed context size.")

        tokens = Tensor(self._context)
        logit: Tensor = self._model(tokens[torch.newaxis, :])
        index = int(logit[0, :].argmax().item())
        return logit, index

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
