import string
from collections.abc import Mapping
from enum import StrEnum
from typing import Iterator, Sequence


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
        valid_chars = string.ascii_letters + string.digits + "+-*/^()" + " \n"
        for i, c in enumerate(valid_chars):
            self._fwd_map[c] = i
            self._rev_map[i] = c

        # Add in the special control tokens
        for i, tok in enumerate(ControlToken, len(self._fwd_map)):
            self._fwd_map[tok] = i
            self._rev_map[i] = tok

        assert len(self._fwd_map) == len(self._rev_map)

    @property
    def forward_map(self) -> Mapping[str, int]:
        """The string to token ID mapping."""
        return self._fwd_map

    @property
    def reverse_map(self) -> Mapping[int, str]:
        """The token ID to string mapping."""
        return self._rev_map

    @property
    def num_tokens(self) -> int:
        """The number of tokens that the tokenizer recognizes."""
        return len(self._fwd_map)

    def to_tokens(self, input: str) -> Iterator[int]:
        """Convert a string into a token sequence.

        Parameters
        ----------
        input : str
            input string

        Yields
        ------
        int
            the next token ID
        """
        input_iter = iter(input)
        for token in self._get_next_token(input_iter):
            try:
                yield self._fwd_map[token]
            except KeyError as e:
                raise RuntimeError(f"Unknown string sequence '{token}'.") from e

    def from_tokens(self, tokens: Sequence[int]) -> Iterator[str]:
        """Convert the tokens back into a character sequence.

        Parameters
        ----------
        tokens : int sequence
            a list or other sequence of token IDs

        Yields
        ------
        str
            the string for each token
        """
        for token_id in tokens:
            try:
                yield self._rev_map[token_id]
            except KeyError as e:
                raise RuntimeError(f"Unknown token ID '{token_id}'.") from e

    def _get_next_token(self, chars: Iterator[str]) -> Iterator[str]:
        ctrl_token = False
        token = ""

        try:
            while True:
                ch = next(chars)

                # Special handling for control tokens.  These take the form of
                # '{tag=}' or '{=tag}', where 'tag' is a string for the specific
                # token.  Whenever a '{' or '}' is encountered then everything
                # inside must be collected into a single string.
                if ctrl_token:
                    token += ch
                    if ch == "}":
                        ctrl_token = False
                    else:
                        continue
                else:
                    token += ch
                    if ch == "{":
                        ctrl_token = True
                        continue

                yield token

                if not ctrl_token:
                    token = ""

        except StopIteration:
            pass

        if ctrl_token:
            raise RuntimeError(f"Unclosed control token '{token}'.")
