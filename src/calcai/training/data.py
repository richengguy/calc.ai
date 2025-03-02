from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterator, TextIO, overload


@dataclass(frozen=True)
class SampleData:
    script: str
    """The script or characters that will be sent into the language model."""

    result: int
    """The output from running the script through the VM."""

    def to_json(self) -> str:
        """Convert the data into a JSON-encoded string.

        The output is designed to be jsonlines-friendly so the string contains
        no newlines.

        Returns
        -------
        str
            a JSON-encoded string
        """
        data = {"script": self.script, "result": self.result}
        return json.dumps(data, separators=(",", ":"), indent=None)

    @staticmethod
    def from_json(string: str) -> "SampleData":
        """Convert a JSON-encoded string into its object representation.

        Parameters
        ----------
        string : str
            JSON-encoded string

        Returns
        -------
        :class:`SampleData`
            object representation
        """
        data = json.loads(string)
        try:
            return SampleData(data["script"], data["result"])
        except KeyError as exc:
            raise RuntimeError(
                f"JSON object is missing the {exc.args[0]} key."
            ) from exc


class SampleWriter:
    """Write out sample data to a JSON lines file."""

    def __init__(self, path: Path) -> None:
        """
        Parameters
        ----------
        path : path instance
            path to the output file
        """
        self._path = path
        self._io: TextIO | None = None

    def __enter__(self) -> "SampleWriter":
        self._io = self._path.open("wt")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool | None:
        if io := self._io:
            io.close()
            self._io = None
        return None

    def write(self, sample: SampleData) -> None:
        """Write a sample to the output file.

        Parameters
        ----------
        sample : :class:`SampleData`
            sample data
        """
        if self._io is None:
            raise RuntimeError("This can only be called in a context manager.")

        self._io.write(f"{sample.to_json()}\n")


def from_jsonlines(path: Path) -> Iterator[SampleData]:
    """Load sample data from a JSON lines file.

    Parameters
    ----------
    path : path instance
        path to a JSON lines file

    Yields
    ------
    :class:`SampleData`
        sample data instance
    """
    with path.open("rt") as f:
        for i, line in enumerate(f):
            try:
                yield SampleData.from_json(line)
            except RuntimeError as exc:
                raise RuntimeError(f"{i}: {exc.args[0]}")
