from dataclasses import dataclass
from random import Random
from typing import Callable

import torch
from torch import Tensor
from torch.nn.functional import cross_entropy
from torch.optim import Adam

from ..model import CalculatorLanguageModel, Query
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
    """Compute the mean sample loss.

    The sample loss is a modified version of the training loss used during
    validation.  Here, it will continue generating predictions until the model
    returns a "RESULT_STOP" token.  A penalty term, proportional to the length
    difference, is added when the two sequences don't match.
    """
    query = Query(sample.script, result=sample.result)
    query.show_result(True)

    expected_str = str(query)
    expected_tokens = list(model.tokenizer.to_tokens(expected_str))
    actual_tokens = []

    start_ind = next(
        i
        for i, token in enumerate(expected_tokens)
        if token == model.tokenizer.start_token
    )
    total_loss = torch.zeros((1,))
    num_generated = 1

    actual_tokens = expected_tokens[: (start_ind + 1)]
    logit, predicted = model.inference_step(actual_tokens, init=True)
    while model.current_context_size < model.max_context_size:
        actual_tokens.append(predicted)

        # If we can still address an expected token, then we can compare the
        # model's output from the expected output.  If not, then it means the
        # model is still generating characters and we should apply a blanket
        # penalty.
        i = start_ind + num_generated
        if i < len(expected_tokens):
            total_loss += cross_entropy(logit, torch.tensor([expected_tokens[i]]))
        else:
            total_loss += 10

        if predicted == model.tokenizer.stop_token:
            break

        logit, predicted = model.inference_step([predicted])

    # Same logic as in the sampling loop.  The two sequences should have the
    # same length.
    size_difference = len(actual_tokens) - len(expected_tokens)
    if size_difference > 0:
        total_loss += 10 * size_difference

    total_loss /= num_generated
    return total_loss, expected_tokens, actual_tokens


def _compute_training_loss(
    sample: SampleData, model: CalculatorLanguageModel
) -> Tensor:
    """Compute the training loss.

    The training loss is computed by seeing how close the predicted sequence is
    to the actual input sequence.  The length of the output is dictated by the
    length of the input, since this is asking the model to generate the same
    number of tokens.  This is what's used for backpropagation.
    """
    query = Query(sample.script, result=sample.result)
    query.show_result(True)

    expected_str = str(query)
    expected_tokens = list(model.tokenizer.to_tokens(expected_str))

    start_ind = next(
        i
        for i, token in enumerate(expected_tokens)
        if token == model.tokenizer.start_token
    )

    total_loss = torch.zeros((1,))
    num_generated = 1

    for i in range(start_ind + 1, len(expected_tokens)):
        logit, predicted = model.inference_step(expected_tokens[:i], init=True)
        total_loss += cross_entropy(logit, torch.tensor([expected_tokens[i]]))
        logit, predicted = model.inference_step([predicted])
        num_generated += 1

    return total_loss / num_generated


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
        test_accuracy: list[tuple[float, float]] = []

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
                # loss, expected, actual = _compute_sample_loss(sample, model)
                loss = _compute_training_loss(sample, model)

                loss.backward()
                optimizer.step()
                optimizer.zero_grad()

                if callback is not None:
                    with torch.no_grad():
                        loss, expected, actual = _compute_sample_loss(sample, model)

                    expected_str = "".join(model.tokenizer.from_tokens(expected))
                    actual_str = "".join(model.tokenizer.from_tokens(actual))
                    last_epoch_loss = None if len(test_loss) == 0 else test_loss[-1]
                    last_epoch_accuracy = (
                        None if len(test_accuracy) == 0 else test_accuracy[-1]
                    )
                    callback(
                        TrainingIteration(
                            n,
                            i,
                            expected_str,
                            actual_str,
                            loss.item(),
                            last_epoch_loss,
                            last_epoch_accuracy,
                        )
                    )

            # Now run through the test samples.  This is the same calculation as
            # used for the backprogation, but without any gradient updates.
            with torch.no_grad():
                model.pytorch_model.eval()

                num_samples = len(self._testing_data)
                num_correct = 0
                num_invalid = 0

                epoch_loss = torch.zeros((1,))
                for sample in self._testing_data:
                    loss, _, output = _compute_sample_loss(sample, model)
                    epoch_loss += loss

                    try:
                        answer = Query.parse(output, model.tokenizer)
                        if answer.result == sample.result:
                            num_correct += 1
                    except ValueError:
                        num_invalid += 1

                test_loss.append(epoch_loss.item() / len(self._testing_data))
                test_accuracy.append(
                    (num_correct / num_samples, num_invalid / num_samples)
                )

        return training_loss, test_loss
