class WorkingSpace:
    """A scratch pad for storing calculation variables."""
    def __init__(self) -> None:
        self._data: dict[str, int] = dict()

    def store(self, key: str, value: int) -> None:
        self._data[key] = value

    def load(self, key: str) -> int:
        return self._data[key]
