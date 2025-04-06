from dataclasses import dataclass
from random import Random
from typing import Callable

import torch
from torch import Tensor
from torch.nn.functional import cross_entropy
from torch.optim import Adam

from ..model import (
    CalculatorLanguageModel,
    Query
)
from .data import SampleData


@dataclass(frozen=True)
class TrainingIteration:
    """Information about a training iteration.

    This class is the argument to a training iteration callback.
    """

    epoch: int
    """Epoch number."""
    iteration: int
    """Iteration number."""
    expected: str
    """The sample the model was being trained on."""
    actual: str
    """What the model actually generated"""
    loss: float
    """The training loss, averaged over the number of generated tokens."""
    test_loss: float | None
    """The test loss, calculated for the *last* epoch."""
    test_accuracy: tuple[float, float] | None
    """The test accuracy, calculated for the *last* epoch.

    This tuple contains two related values.  First is the accuracy, or ratio of
    test samples where the inference result exactly match the calculated result.

    Second is the ratio of "invalid" results.  This is the subset of failures
    where the model generated a syntactically incorrect results.  These are
    cases where the response wasn't well-formed (missing a "stop" token) or the
    result cannot be parsed as an integer.
    """


TrainingCallback = Callable[[TrainingIteration], None]


def _compute_sample_loss(
    sample: SampleData, model: CalculatorLanguageModel
) -> tuple[Tensor, list[int], list[int]]:
    query = Query(sample.script, result=sample.result)

    query.show_result(True)
    expected_str = str(query)

    query.show_result(False)
    query_str = str(query)

    expected_tokens = list(model.tokenizer.to_tokens(expected_str))
    actual_tokens = list(model.tokenizer.to_tokens(query_str))

    start_expected = len(actual_tokens)

    sample_loss = torch.zeros((1,))
    num_generated = 1

    logit, token = model.inference_step(actual_tokens, init=True)
    for expected in expected_tokens[start_expected:]:
        # Compute the token loss and add it to the total sample loss.  It will
        # be averages across all samples.
        token_loss = cross_entropy(logit, torch.tensor([expected]))
        sample_loss += token_loss

        # Keep track of what the model actual produces.
        actual_tokens.append(token)

        # Generate the next token and see how close it got to the expected
        # result.
        logit, token = model.inference_step(actual_tokens)
        num_generated += 1

    sample_loss /= num_generated
    return sample_loss, expected_tokens, actual_tokens


class ModelTrainer:
    """Trains the language model using auto-generated training data.

    The trainer uses expressions that were automatically generated and then
    evaluated by the calc.ai interpreter.  The complexity of the data then
    defines what the language model is able to do.

    There is an optional data augmentation step where new samples are created by
    randomly adding or remove some whitespace from the input expression string.
    """

    def __init__(
        self,
        data: list[SampleData],
        *,
        testing_split: float = 0.2,
        epochs: int = 5,
        whitespace_rate: float | None = None,
        seed: int | None = None,
    ) -> None:
        """
        Parameters
        ----------
        data : list of SampleData
            input training data
        testing_split : float
            the fraction of the training data withheld from the model during
            training; defaults to 0.2 or 20% is used for testing
        epochs : int
            the number of times the model goes through all of the training data,
            defaults to '5'
        whitespace_rate : float, optional
            specifies how likely a whitespace charater is to be removed or added
            to a training sample; defaults to `None` or "off"
        seed : int, optional
            controls the PRNG seed used for the various training steps
        """
        if whitespace_rate is not None:
            raise NotImplementedError("Data augmentation is not yet implemented.")

        if len(data) == 0:
            raise ValueError("Training data is empty.")

        num_test = int(testing_split * len(data))

        if num_test < 0 or num_test > len(data):
            raise ValueError(f"Cannot use {testing_split} as the testing split.")

        self._rng = Random(seed)
        self._seed = seed
        self._epochs = epochs

        # This is how Python recommends shuffling an immutable list
        # See https://docs.python.org/3.12/library/random.html#random.shuffle
        shuffled_data = self._rng.sample(data, k=len(data))
        self._testing_data = shuffled_data[:num_test]
        self._training_data = shuffled_data[num_test:]

    @property
    def training_samples(self) -> int:
        """The number of samples used for training, out of the total training set."""
        return len(self._training_data)

    def train(
        self,
        model: CalculatorLanguageModel,
        *,
        callback: TrainingCallback | None = None,
    ) -> tuple[list[float], list[float]]:
        """Train a language model.

        Parameters
        ----------
        model : CalculatorLanguageModel
            language model instance
        callback : callable
            a callback used to report on training status

        Returns
        -------
        training_loss : list of float
            per-iteration training losss
        test_loss : list of float
            per-epoch testing loss
        """
        training_loss: list[float] = []
        test_loss: list[float] = []

        if seed := self._seed:
            torch.manual_seed(seed)
        else:
            torch.seed()

        optimizer = Adam(model.pytorch_model.parameters())

        for n in range(self._epochs):
            self._rng.shuffle(self._training_data)

            # Run through all of the training samples and update the model
            # weights.  If a callback is provided then it is called after the
            # sample is processed.
            model.pytorch_model.train()
            for i, sample in enumerate(self._training_data):
                loss, expected, actual = _compute_sample_loss(sample, model)

                loss.backward()
                optimizer.step()
                optimizer.zero_grad()

                if callback is not None:
                    expected_str = "".join(model.tokenizer.from_tokens(expected))
                    actual_str = "".join(model.tokenizer.from_tokens(actual))
                    last_epoch_loss = None if len(test_loss) == 0 else test_loss[-1]
                    callback(
                        TrainingIteration(
                            n,
                            i,
                            expected_str,
                            actual_str,
                            loss.item(),
                            last_epoch_loss,
                            None,
                        )
                    )

            # Now run through the test samples.  This is the same calculation as
            # used for the backprogation, but without any gradient updates.
            with torch.no_grad():
                model.pytorch_model.eval()
                epoch_loss = torch.zeros((1,))
                for sample in self._testing_data:
                    loss, _, _ = _compute_sample_loss(sample, model)
                    epoch_loss += loss

                test_loss.append(epoch_loss.item() / len(self._testing_data))

        return training_loss, test_loss
