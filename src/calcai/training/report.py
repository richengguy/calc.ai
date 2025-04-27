from pathlib import Path

import jinja2
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import ArrayLike, NDArray

from .trainer import TrainingSummary


class Report:
    """Generates a report showing the results of a training session."""

    def __init__(self, *, smoothing_window: int = 50) -> None:
        self._env = jinja2.Environment(loader=jinja2.PackageLoader(__package__))

        pad_lower = smoothing_window // 2
        pad_upper = smoothing_window // 2
        if smoothing_window % 2 == 0:
            pad_upper -= 1

        self._padding = [pad_lower, pad_upper]
        self._window = np.ones(smoothing_window) / 50

    def write(self, model_name: str, summary: TrainingSummary, path: Path) -> Path:
        """Write a report from a training summary.

        Parameters
        ----------
        summary: :class:`TrainingSummary`
            a training summary
        path : Path
            directory where the report is saved
        """
        path.mkdir(parents=True)

        readme_path = path / "README.md"
        training_loss_png = path / "training-loss.png"
        validation_loss_png = path / "validation-loss.png"
        validation_accuracy_png = path / "test-accuracy.png"

        # Create the training loss figure.
        training_loss: list[float] = []
        for epoch_loss in summary.training_loss:
            training_loss.extend(epoch_loss)

        smoothed_loss = self._smooth_sequence(training_loss)

        fig, ax = plt.subplots()
        ax.plot(training_loss, label="Original")
        ax.plot(smoothed_loss, label="Smoothed")
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Loss")
        ax.legend()
        fig.savefig(training_loss_png)

        # Create the validation loss figure.
        fig, ax = plt.subplots()
        ax.plot(summary.validation_loss)
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Loss")
        fig.savefig(validation_loss_png)

        # Create the validation accuracy figure.
        fig, ax = plt.subplots()
        ax.plot(
            [100 * accuracy for accuracy, _ in summary.validation_accuracy],
            label="Accuracy",
        )
        ax.plot(
            [100 * invalid for _, invalid in summary.validation_accuracy],
            label="Invalid",
        )
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Percentage (%)")
        ax.legend()
        fig.savefig(validation_accuracy_png)

        # Generate the report README.
        template = self._env.get_template("report.md.j2")
        final_accuracy, final_invalids = summary.validation_accuracy[-1]
        readme = template.render(
            model_name=model_name,
            epochs=summary.epochs,
            accuracy=final_accuracy,
            invalid=final_invalids,
            images={
                "training_loss": training_loss_png,
                "validation_loss": validation_loss_png,
                "validation_accuracy": validation_accuracy_png,
            },
        )
        with readme_path.open("wt") as f:
            f.write(readme)

        return path

    def _smooth_sequence(self, arr: ArrayLike) -> NDArray:
        padded = np.pad(arr, self._padding, mode="edge")
        return np.convolve(padded, self._window, mode="valid")
