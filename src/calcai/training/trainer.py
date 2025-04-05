import torch
from torch import Tensor
from torch.nn import CrossEntropyLoss
from torch.optim import Adam

from random import Random
from typing import Callable

from ..model import CalculatorLanguageModel, create_query
from .data import SampleData

TrainingCallback = Callable[[float, str, str, int], None]


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

    def train(self, model: CalculatorLanguageModel, *, callback: TrainingCallback | None = None) -> tuple[list[float], list[float]]:
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
        cross_entropy_loss = CrossEntropyLoss()

        for n in range(self._epochs):
            self._rng.shuffle(self._training_data)
            for i, sample in enumerate(self._training_data):
                answer = list(model.tokenizer.to_tokens(create_query(sample.script, answer=sample.result)))
                query = list(model.tokenizer.to_tokens(create_query(sample.script)))

                iter_losses: list[float] = []

                logit, token = model.training_step(query, init=True)
                for expected in answer[len(query):]:
                    # Calculate the cross-entropy loss
                    loss: Tensor = cross_entropy_loss(logit, Tensor([expected]))
                    loss.backward()
                    iter_losses.append(loss.item())

                    # Update the optimizer
                    optimizer.step()
                    optimizer.zero_grad()

                    # Update the query and then send it back into the language model.
                    query.append(token)
                    logit, token = model.training_step(query)

        return training_loss, test_loss
