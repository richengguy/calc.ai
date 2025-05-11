from dataclasses import KW_ONLY, dataclass
from pathlib import Path
from types import TracebackType

import jinja2
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import ArrayLike, NDArray
from rich import box
from rich.console import Console, ConsoleOptions, RenderResult
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, TaskID
from rich.table import Table
from rich.text import Text

from .trainer import TrainingIteration, TrainingSummary


@dataclass
class _Tasks:
    _: KW_ONLY
    overall: TaskID
    epoch: TaskID


class ProgressDisplay:
    def __init__(self, console: Console, epochs: int, samples: int) -> None:
        self._progress = Progress(console=console)
        self._epochs = epochs
        self._samples = samples
        self._tasks: _Tasks | None = None

    def update(self, step: TrainingIteration) -> None:
        """Update the training progress display.

        Parameters
        ----------
        step : :class:`TrainingIteration`
            the current training step
        """
        if self._tasks is None:
            self._tasks = _Tasks(
                overall=self._progress.add_task(
                    "Overall", total=self._epochs * self._samples
                ),
                epoch=self._progress.add_task(
                    f"Epoch {step.epoch}", total=self._samples
                ),
            )

        if step.iteration == 0:
            self._progress.remove_task(self._tasks.epoch)
            self._tasks.epoch = self._progress.add_task(
                f"Epoch {step.epoch}", total=self._samples
            )

        self._progress.update(self._tasks.overall, advance=1)
        self._progress.update(self._tasks.epoch, advance=1)

    def __rich__(self) -> Progress:
        return self._progress


class TrainingDisplay:
    def __init__(self, step: TrainingIteration) -> None:
        model = Table(expand=True, show_header=False, box=box.MINIMAL)
        model.add_row(f"Ground Truth » {step.expected}")
        model.add_row(f"CLM Response » {step.actual}")
        model.add_section()
        model.add_row(f"Loss         » {step.loss}")

        self._panel = Panel(
            model, title=f"Epoch {step.epoch} :: Iteration {step.iteration}"
        )

    def __rich__(self) -> Panel:
        return self._panel


class ConsoleDisplay:
    def __init__(self, max_lines: int = 10) -> None:
        self._max_lines = max_lines
        self._lines: list[str] = []

    def print(self, msg: str) -> None:
        self._lines.append(msg)
        if len(self._lines) > self._max_lines:
            self._lines = self._lines[-self._max_lines :]

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        self._max_lines = options.height or options.size.height
        table = Table.grid()
        for line in self._lines:
            table.add_row(Text.from_markup(line, overflow="ellipsis"))
        yield table


class ValidationStatus:
    def __init__(self, step: TrainingIteration) -> None:
        def as_prcnt(num: float | None) -> str:
            if num is None:
                return " N/A"
            return f" {num * 100:.3g}%"

        epoch_loss = " N/A" if step.test_loss is None else f" {step.test_loss}"
        if step.test_accuracy is None:
            epoch_accuracy = None
            epoch_invalid = None
        else:
            epoch_accuracy, epoch_invalid = step.test_accuracy

        self._items = Table.grid()
        self._items.add_column(justify="right")
        self._items.add_column(justify="left")
        self._items.add_row("Test Loss :arrow_forward: ", epoch_loss)
        self._items.add_row("Accuracy :arrow_forward: ", as_prcnt(epoch_accuracy))
        self._items.add_row("Invalid :arrow_forward: ", as_prcnt(epoch_invalid))

    def __rich__(self) -> Table:
        return self._items


class StatusDisplay:
    """Shows a live display with the current training status."""

    def __init__(self, console: Console, epochs: int, samples: int) -> None:
        self._layout = Layout()
        self._layout.split_row(Layout(name="overall"), Layout(name="training"))

        self._layout["overall"].split_column(
            Layout(name="progress"), Layout(name="logging")
        )

        self._progress = ProgressDisplay(console, epochs, samples)
        self._console = ConsoleDisplay()

        self._overall_pane = Layout()
        self._overall_pane.split_column(
            Layout(self._progress, name="progbar"), Layout(name="validation")
        )

        self._overall_pane["validation"].visible = False

        self._layout["training"].size = None
        self._layout["training"].ratio = 3

        self._layout["overall"].minimum_size = 40
        self._layout["overall"].ratio = 2
        self._layout["overall"]["progress"].update(
            Panel(self._overall_pane, title="Progress")
        )
        self._layout["overall"]["logging"].update(Panel(self._console, title="Info"))
        self._layout["overall"]["logging"].visible = False

        self._display = Live(console=console, screen=True)

    def __enter__(self) -> "StatusDisplay":
        self._display.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        self._display.stop()
        return None

    def print(self, msg: str) -> None:
        self._layout["overall"]["logging"].visible = True
        self._console.print(msg)

    def update(self, iteration: TrainingIteration) -> None:
        self._progress.update(iteration)

        if iteration.iteration == 0 or iteration.iteration % 100 == 0:
            self._overall_pane["validation"].visible = True
            self._overall_pane["validation"].update(ValidationStatus(iteration))
            self._layout["training"].update(TrainingDisplay(iteration))

        self._display.update(self._layout)


class SessionReport:
    """Generates a report showing the results of a training session."""

    def __init__(self, *, smoothing_window: int = 50) -> None:
        self._env = jinja2.Environment(
            loader=jinja2.PackageLoader(__package__),
            trim_blocks=True,
            lstrip_blocks=True,
        )

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
            results=summary.results,
        )
        with readme_path.open("wt") as f:
            f.write(readme)

        return path

    def _smooth_sequence(self, arr: ArrayLike) -> NDArray:
        padded = np.pad(arr, self._padding, mode="edge")
        return np.convolve(padded, self._window, mode="valid")
