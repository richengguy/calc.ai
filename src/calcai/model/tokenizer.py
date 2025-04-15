import string
from collections.abc import Mapping
from enum import StrEnum
from hashlib import blake2b
from typing import Iterator, Sequence


class ControlToken(StrEnum):
    """Control tokens used to control lanuage model actions."""

    NULL = "{null}"
    """Used when a result cannot be computed.

    This will happen with expressions such as '5 / 0', where the result is a
    "division by zero" error.
    """

    EXPR_START = "{expr=}"
    """Denotes the start of a arithmetic expression script.

    The script acts as the input into the language model.  The tokens between
    the expression start and end tokens will be something like
    '1 + 2 * (3 + 4)'.
    """

    EXPR_STOP = "{=expr}"
    """Denotes the end of a arithmetic expression script."""

    SOLUTION_START = "{solution=}"
    """Denotes the start of a solution block.

    A solution lists out out how to solve the expression inside of an expression
    block.  There may be multiple parts to the solution, all separated by a
    newline.
    """

    SOLUTION_STOP = "{=solution}"
    """Denotes the end of a solution block."""

    RESULT_START = "{result=}"
    """Denotes the start of a result block.

    The contents of the block should only be number tokens, and possibly a single
    '-' token, since this represents the result of a computation.
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

    @property
    def start_token(self) -> int:
        """The ID of the result "start" token."""
        return self._fwd_map[ControlToken.RESULT_START]

    @property
    def stop_token(self) -> int:
        """The ID of the result "stop" token."""
        return self._fwd_map[ControlToken.RESULT_STOP]

    def control_id(self, token: ControlToken) -> int:
        """Get the ID for a control token."""
        return self._fwd_map[token]

    def control_token_from_id(self, id: int) -> ControlToken | None:
        """Converts a token ID into a control token.

        Parameters
        ----------
        id : int
            token ID

        Returns
        -------
        ControlToken or `None`
            the control token or `None` if it is something else
        """
        str_rep = self._rev_map[id]
        if str_rep in ControlToken:
            return ControlToken(str_rep)
        return None

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
                raise ValueError(f"Unknown string sequence '{token}'.") from e

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
                raise ValueError(f"Unknown token ID '{token_id}'.") from e

    def str_to_tokens(self, input: str) -> list[int]:
        """Converts a string into a token list.

        Parameters
        ----------
        input : str
            input string

        Returns
        ------
        list of int
            token sequence
        """
        return list(self.to_tokens(input))

    def tokens_to_str(self, tokens: Sequence[int]) -> str:
        """Convert tokens into a string.

        Parameters
        ----------
        tokens : int sequence
            a list or other sequence of token IDs

        Returns
        -------
        str
            the string representation
        """
        return "".join(self.from_tokens(tokens))

    def version_hash(self) -> str:
        """A hash used for versioning the tokenizer.

        The hash is generated from the set of characters the tokenizer can
        process.  This is used to when serializing a model to ensure that the
        current tokenizer can support the loaded model.

        Returns
        -------
        str
            a string hash
        """
        hash = blake2b()
        for ch in self._fwd_map:
            hash.update(ch.encode())
        return hash.hexdigest()

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
            raise ValueError(f"Unclosed control token '{token}'.")


class Query:
    """Represents the data being sent into and produced by the language model.

    The query is a specially-formatted string that is sent into the language
    model for processing.  The model will then respond with a similarly
    formatted string.  The Query object is also able to parse the input/output
    responses.
    """

    def __init__(self, expr: str, *, result: int | None = None) -> None:
        """
        Parameters
        ----------
        expr : str
            input expression
        result : int, optional
            if set, the query will also contain result output tags
        """

        self.expr = expr
        """The expression portion of the model query."""

        self.result = result
        """The solution to a given expression."""

        self._show_result = result is not None

    def show_result(self, show: bool) -> None:
        """Enable/disable showing the contents of the result tags.

        The default behaviour is to only show a result tag if one was provided
        when the query was created.  This can be overridden to, for instance,
        create training data.

        Parameters
        ----------
        show : bool
            enable/disable result output
        """
        self._show_result = show

    def __str__(self) -> str:
        parts: list[str] = []
        parts.append(
            f"{ControlToken.EXPR_START}{self.expr}{ControlToken.EXPR_STOP}{ControlToken.RESULT_START}"  # noqa: E501
        )

        if self._show_result:
            result_str = ControlToken.NULL if self.result is None else str(self.result)
            parts.append(f"{result_str}{ControlToken.RESULT_STOP}")

        return "".join(parts)

    @staticmethod
    def parse(query: str | list[int], tokenizer: Tokenizer) -> "Query":
        """Parse a string and convert it into a Query object.

        The query parsing uses a tokenize for the inital string preprocessing.
        The parser then looks for the following pattern:

        ```
        {expr=}some expression{=expr}{result=}result{=result}
        ```

        Parameters
        ----------
        query : str or list[int]
            input query string or a list of token IDs
        tokenizer : Tokenizer
            tokenizer instance

        Returns
        -------
        Query
            the parsed Query object

        Raises
        ------
        ValueError
            if the query string could not be parsed
        """
        if isinstance(query, str):
            token_stream = tokenizer.to_tokens(query)
        else:
            token_stream = iter(query)

        # Make sure that we're in the start of an expression statement.
        if next(token_stream) != tokenizer.control_id(ControlToken.EXPR_START):
            raise ValueError(f"Query must start with a {ControlToken.EXPR_START}.")

        # Collect all of the tokens in the expression statement.  Any control
        # tokens inside of this section means something is wrong with the query.
        hit_expr_stop = False
        expr_tokens: list[int] = []
        for token in token_stream:
            if ctrl_token := tokenizer.control_token_from_id(token):
                if ctrl_token == ControlToken.EXPR_STOP:
                    hit_expr_stop = True
                    break
                else:
                    raise ValueError(f"Unexpected {ctrl_token} control token.")

            expr_tokens.append(token)

        if not hit_expr_stop:
            raise ValueError(f"Did not encounter a closing {ControlToken.EXPR_STOP}.")

        expr = "".join(tokenizer.from_tokens(expr_tokens))

        # Check to see if there's anything more to process.  If not, create a
        # query.  If there is more to process then it must be the token used to
        # indicate the start of a result statement.
        try:
            if next(token_stream) != tokenizer.control_id(ControlToken.RESULT_START):
                raise ValueError(
                    f"Result must start with a {ControlToken.RESULT_START}."
                )
        except StopIteration:
            return Query("".join(tokenizer.from_tokens(expr_tokens)))

        # Now collect the contents of the result statement.
        hit_result_stop = False
        result_tokens: list[int] = []
        for token in token_stream:
            if ctrl_token := tokenizer.control_token_from_id(token):
                if ctrl_token == ControlToken.RESULT_STOP:
                    hit_result_stop = True
                    break
                elif ctrl_token != ControlToken.NULL:
                    raise ValueError(f"Unexpected {ctrl_token} control token.")

            result_tokens.append(token)

        if not hit_result_stop:
            raise ValueError(f"Did not encounter a closing {ControlToken.RESULT_STOP}.")

        result_str = "".join(tokenizer.from_tokens(result_tokens))
        result = None if result_str == ControlToken.NULL else int(result_str)

        return Query(expr, result=result)
