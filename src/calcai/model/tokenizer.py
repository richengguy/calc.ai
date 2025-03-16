from enum import StrEnum
import string


class ControlToken(StrEnum):
    """Control tokens used to control lanuage model actions."""
    EXPR_START = "{expr=}"
    """Denotes the start of a arithmetic expression script.

    The script acts as the input into the language model.  The tokens between
    the expression start and end tokens will be something like
    '1 + 2 * (3 + 4)'.
    """

    EXPR_STOP = "{=expr}"
    """Denotes the end of a arithmetic expression script."""

    RESULT_START = "{result=}"
    """Denotes the start of a result block.

    The contents of the block should only be number tokens, since this
    represents the result of a computation.
    """

    RESULT_STOP = "{=result}"
    """Denotes the end of a result block."""


class Tokenizer:
    """Maps between characters and language model tokens."""
    def __init__(self) -> None:
        self._fwd_map: dict[str, int] = {}
        self._rev_map: dict[int, str] = {}

        # Add in all the usual alphanumeric characters, including punctuation
        # and whitespace (only ' ' and '\n', no tabs)
        valid_chars = string.ascii_letters + string.digits + '+-*/^()' + ' \n'
        for i, c in enumerate(valid_chars):
            self._fwd_map[c] = i
            self._rev_map[i] = c

        # Add in the special control tokens
        for i, tok in enumerate(ControlToken, len(self._fwd_map)):
            self._fwd_map[tok] = i
            self._rev_map[i] = tok

        assert len(self._fwd_map) == len(self._rev_map)
