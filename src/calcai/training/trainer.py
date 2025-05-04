from dataclasses import dataclass
from random import Random
from typing import Callable

import torch
from torch import Tensor
from torch.nn.functional import cross_entropy
from torch.optim import Adam
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Dataset

from ..model import CalculatorLanguageModel, ControlToken, Query
from ..model.tokenizer import Tokenizer
from .data import SampleData

TrainingCallback = Callable[["TrainingIteration"], None]


@dataclass
class _TrainingSample:
    expected: str
    tokens: Tensor
    input_end: int
    answer: int | None


class _TrainingDataset(Dataset[_TrainingSample]):
    def __init__(
        self, samples: list[SampleData], tokenizer: Tokenizer, device: torch.device
    ) -> None:
        self._data: list[_TrainingSample] = []
        for sample in samples:
            query = Query(sample.script, result=sample.result, steps=sample.steps)
            query.show_result(True)

            expected = str(query)
            tokens = torch.tensor(
                tokenizer.str_to_tokens(expected), dtype=torch.long, device=device
            )

            input_end = next(
                i
                for i, token in enumerate(tokens)
                if token == tokenizer.control_id(ControlToken.EXPR_STOP)
            )

            self._data.append(
                _TrainingSample(expected, tokens, input_end, sample.result)
            )

    def __getitem__(self, index: int) -> _TrainingSample:
        return self._data[index]

    def __len__(self) -> int:
        return len(self._data)


def _convert_tensor(t: Tensor) -> list[int]:
    return [int(t[i].item()) for i in range(t.shape[0])]


@dataclass(frozen=True)
class ValidationResult:
    """Model output generated during validation."""

    ground_truth: str
    model_output: str
    passed: bool
    valid: bool


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
    """What the model actually generated."""
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


@dataclass(frozen=True)
class TrainingSummary:
    training_loss: list[list[float]]
    """The training loss for each iteration, by epoch."""
    validation_loss: list[float]
    """The test loss for each epoch.

    This value is similar to the training loss, but also penalizes the CLM's
    output if it isn't the same length as the ground truth.  These losses are
    only used for reporting and not part of the optimization.
    """
    validation_accuracy: list[tuple[float, float]]
    """The validation accuracy for each epoch.

    Each element contains two values: the accuracy, which is
    the percentage of correct answers, and the percentage of CLM outputs that
    cannot even be parsed.
    """

    results: list[ValidationResult]
    """The model output after the final validation stage."""

    @property
    def epochs(self) -> int:
        return len(self.validation_loss)


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
        device: torch.device | None = None,
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
        device : torch.device, optional
            device used for training; defaults to 'cpu'
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
        self._device = torch.device("cpu") if device is None else device

        # This is how Python recommends shuffling an immutable list
        # See https://docs.python.org/3.12/library/random.html#random.shuffle
        shuffled_data = self._rng.sample(data, k=len(data))
        self._validation_data = shuffled_data[:num_test]
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
    ) -> TrainingSummary:
        """Train a language model.

        Parameters
        ----------
        model : CalculatorLanguageModel
            language model instance
        callback : callable
            a callback used to report on training status

        Returns
        -------
        :class:`TrainingSummary`
            summary of training and validation losses
        """
        training_loss: list[list[float]] = []
        validation_loss: list[float] = []
        validation_accuracy: list[tuple[float, float]] = []
        final_results: list[ValidationResult] = []

        if seed := self._seed:
            torch.manual_seed(seed)
        else:
            torch.seed()

        optimizer = Adam(model.pytorch_model.parameters())
        scheduler = CosineAnnealingLR(optimizer, self._epochs)

        training_dataset = _TrainingDataset(
            self._training_data, model.tokenizer, self._device
        )
        validation_dataset = _TrainingDataset(
            self._validation_data, model.tokenizer, self._device
        )

        training_loader = DataLoader(
            training_dataset,
            batch_size=None,
            shuffle=True,
            pin_memory=True,
            pin_memory_device=str(self._device),
        )
        validation_loader = DataLoader(
            validation_dataset,
            batch_size=None,
            shuffle=False,
            pin_memory=True,
            pin_memory_device=str(self._device),
        )

        for n in range(self._epochs):
            self._rng.shuffle(self._training_data)
            iter_loss: list[float] = []

            sample: _TrainingSample

            # Run through all of the training samples and update the model
            # weights.  If a callback is provided then it is called after the
            # sample is processed.
            model.pytorch_model.train()
            for i, sample in enumerate(training_loader):
                loss = self._compute_training_loss(sample, model)
                iter_loss.append(loss.item())

                loss.backward()
                optimizer.step()
                optimizer.zero_grad()

                if callback is not None:
                    with torch.no_grad():
                        callback(
                            self._create_callback_struct(
                                sample,
                                model,
                                n,
                                i,
                                loss.item(),
                                validation_loss,
                                validation_accuracy,
                            )
                        )

            if self._epochs > 2:
                scheduler.step()

            training_loss.append(iter_loss)

            # Now run through the test samples.  This is modified version of
            # what's done for the optimization, just without any gradient
            # calculations.  The loss is the *cumulative* prediction error
            # rather than the "next token" prediciton error.
            with torch.no_grad():
                model.pytorch_model.eval()

                num_samples = len(self._validation_data)
                num_correct = 0
                num_invalid = 0

                epoch_loss = torch.zeros((1,))
                for sample in validation_loader:
                    loss, output = self._compute_sample_loss(sample, model)
                    epoch_loss += loss

                    correct = False
                    valid = True

                    try:
                        answer = Query.parse(_convert_tensor(output), model.tokenizer)
                        correct = answer.result == sample.answer
                        if correct:
                            num_correct += 1
                    except ValueError:
                        valid = False
                        num_invalid += 1

                    # Record the validation results on the last epoch.
                    if n == (self._epochs - 1):
                        actual = model.tokenizer.tokens_to_str(_convert_tensor(output))
                        expected = model.tokenizer.tokens_to_str(
                            _convert_tensor(sample.tokens)
                        )
                        final_results.append(
                            ValidationResult(expected, actual, correct, valid)
                        )

                validation_loss.append(epoch_loss.item() / len(self._validation_data))
                validation_accuracy.append(
                    (num_correct / num_samples, num_invalid / num_samples)
                )

        return TrainingSummary(
            training_loss, validation_loss, validation_accuracy, final_results
        )

    def _compute_sample_loss(
        self, sample: _TrainingSample, model: CalculatorLanguageModel
    ) -> tuple[Tensor, Tensor]:
        """Compute the mean sample loss.

        The sample loss is a modified version of the training loss used during
        validation.  Here, it will continue generating predictions until the
        model returns a "RESULT_STOP" token.  A penalty term, proportional to
        the length difference, is added when the two sequences don't match.
        """
        NUM_OVERFLOW_TOKENS = 20
        STOP_TOKEN = torch.tensor(
            model.tokenizer.control_id(ControlToken.RESULT_STOP), device=self._device
        )
        output_length = sample.tokens.shape[0] + NUM_OVERFLOW_TOKENS

        total_loss = torch.zeros((1,), device=self._device)
        num_generated = 1

        # Initialize the memory used for tracking the model output.
        input_tokens = sample.tokens[: (sample.input_end + 1)]
        actual_tokens = torch.zeros(
            (output_length,), device=self._device, dtype=torch.long
        )
        actual_tokens[: (sample.input_end + 1)].copy_(input_tokens)

        # Run the inference loop, but don't bother if it goes beyond a certain
        # length.
        logit = model.inference_step(input_tokens, init=True)
        for i in range(sample.input_end + 1, output_length):
            actual_tokens[i] = logit[0, :].argmax()

            # If we can still address an expected token, then we can compare the
            # model's output from the expected output.  If not, then it means the
            # model is still generating characters and we should apply a blanket
            # penalty.  The choice of '10' is from the fact that this
            # corresponds to a very low likelihood, e.g., exp(-10) << 1
            if i < sample.tokens.shape[0]:
                total_loss += cross_entropy(logit, sample.tokens[torch.newaxis, i])
            else:
                total_loss += 10

            if actual_tokens[i] == STOP_TOKEN:
                break

            logit = model.inference_step(actual_tokens[i])
            num_generated += 1

        # Same logic as in the sampling loop.  The two sequences should have the
        # same length.
        size_difference = i - sample.tokens.shape[0]
        if size_difference > 0:
            total_loss += 10 * size_difference

        total_loss /= num_generated
        return total_loss, actual_tokens[: (i + 1)]

    def _create_callback_struct(
        self,
        sample: _TrainingSample,
        model: CalculatorLanguageModel,
        epoch: int,
        iteration: int,
        sammple_loss: float,
        test_loss: list[float],
        test_accuracy: list[tuple[float, float]],
    ) -> TrainingIteration:
        _, actual = self._compute_sample_loss(sample, model)
        actual = actual.cpu()

        actual_str = model.tokenizer.tokens_to_str(_convert_tensor(actual))
        last_epoch_loss = None if len(test_loss) == 0 else test_loss[-1]
        last_epoch_accuracy = None if len(test_accuracy) == 0 else test_accuracy[-1]
        return TrainingIteration(
            epoch,
            iteration,
            sample.expected,
            actual_str,
            sammple_loss,
            last_epoch_loss,
            last_epoch_accuracy,
        )

    def _compute_training_loss(
        self, sample: _TrainingSample, model: CalculatorLanguageModel
    ) -> Tensor:
        """Compute the training loss.

        The training loss is computed by seeing how close the predicted sequence
        is to the actual input sequence.  The length of the output is dictated
        by the length of the input, since this is asking the model to generate
        the same number of tokens.  This is what's used for backpropagation.
        """
        total_loss = torch.zeros((1,), device=self._device)
        num_generated = 0

        for i in range(sample.input_end + 1, len(sample.tokens)):
            logit = model.inference_step(sample.tokens[:i], init=True)
            total_loss += cross_entropy(logit, sample.tokens[torch.newaxis, i])
            num_generated += 1

        return total_loss / num_generated
