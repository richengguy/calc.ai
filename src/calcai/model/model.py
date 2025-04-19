from pathlib import Path
from typing import Iterator

import torch
from torch import Tensor
from torch.nn import Module

from .layers import SimpleDecoderTransformer
from .tokenizer import ControlToken, Tokenizer


class CalculatorLanguageModel:
    """A simple transformer for computing arithmetic expressions.

    The Calculator Language Model (CLM) will accept a string, something like
    `1 + 2`, and, in theory, generate `3`.
    """

    def __init__(
        self,
        *,
        embedding_dimensions: int = 16,
        max_context: int = 256,
        layers: int = 4,
        attention_heads: int = 2,
        device: torch.device | None = None,
    ) -> None:
        """
        Parameters
        ----------
        embedding_dimensions : int
            size of the token embedding space; defaults to 16
        max_context : int
            maximum number of tokens the model can work with; defaults to 256
        layers : int
            the number of layers in the transformer
        attention_heads : int
            the number of parallel attention heads in each layer
        device : torch.device, optional
            set the device the model runs on; defaults to 'cpu'
        """
        self.tokenizer = Tokenizer()
        self._model = SimpleDecoderTransformer(
            self.tokenizer.num_tokens,
            embedding_dimensions,
            num_layers=layers,
            attention_heads=attention_heads,
        )
        self._max_context = max_context
        self._context: list[int] = []
        self._device = torch.device("cpu")

        # Have the model use the given inference device
        if device is not None:
            self.inference_device = device

    @property
    def current_context_size(self) -> int:
        """Current context window size.

        This corresponds to how much data the model will process the next time
        it performs an inference.
        """
        return len(self._context)

    @property
    def inference_device(self) -> torch.device:
        """The device (i.e. CPU or GPU) the model is running on."""
        return self._device

    @inference_device.setter
    def inference_device(self, device: torch.device) -> None:
        self._device = device
        self._model.to(device)

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
        tokens = list(self.tokenizer.to_tokens(query))

        with torch.no_grad():
            _, _, predicted = self.inference_step(tokens, init=True)
            while self.current_context_size < self.max_context_size:
                yield self.tokenizer.reverse_map[predicted]

                if predicted == self.tokenizer.control_id(ControlToken.RESULT_STOP):
                    break

                _, _, predicted = self.inference_step([predicted])

    def inference_step(
        self, input: list[int], *, init: bool = False
    ) -> tuple[Tensor, Tensor, int]:
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
            the logits vector for model's next predicted token
        result : Tensor
            the predicted numerical value of the token sequence
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

        logit: Tensor
        result: Tensor

        tokens = torch.tensor(self._context, device=self._device)
        logit, result = self._model(tokens[torch.newaxis, :])
        index = int(logit[0, :].argmax().item())
        return logit, result, index

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

        torch.save(
            {
                "_tokenizer": self.tokenizer.version_hash(),
                "_max_context": self._max_context,
                "_model": self._model.state_dict(),
            },
            path,
        )

    @staticmethod
    def load(path: Path) -> "CalculatorLanguageModel":
        """Load a model.

        Parameters
        ----------
        path : Path
            location where the model is saved

        Returns
        -------
        CalculatorLanguageModel
            deserialized model
        """
        expected_hash = Tokenizer().version_hash()
        serialized = torch.load(path, weights_only=True)
        if expected_hash != serialized["_tokenizer"]:
            raise RuntimeError(
                f"Expected tokenizer hash ({expected_hash}) does not match "
                f"serialized hash ({serialized['_tokenizer']})"
            )

        model = CalculatorLanguageModel(max_context=serialized["_max_context"])
        model.pytorch_model.load_state_dict(serialized["_model"], strict=False)
        return model
