from enum import Enum
from typing import Callable

from rich.table import Table

from ._console import console
from ._console import print as cprint
from .model import CalculatorLanguageModel, Query
from .vm import Interpreter

_COMMAND_CHAR = ":"


class _Command(tuple[str, str], Enum):
    HELP = ("help", "Show this help message.")
    CLEAR = ("clear", "Clears the terminal screen.")
    QUIT = ("quit", "Quit the REPL")


class _ReplError(RuntimeError):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)


class Repl:
    """A REPL for interacting with a CLM.

    The REPL provides a frontend for the CLM.  User inputs are converted into
    queries and response tokens are converted back into strings.  The REPL also
    maintains its own :class`Interpreter` so that the CLM results can be
    verified.
    """

    def __init__(
        self,
        model: CalculatorLanguageModel,
        *,
        prompt: str = ">",
        prompt_alt: str = "-",
    ) -> None:
        self._model = model
        self._interpreter = Interpreter()
        self._prompt = prompt
        self._prompt_alt = prompt_alt

        self._commands_long: dict[str, _Command] = {}
        self._commands_short: dict[str, _Command] = {}
        for cmd in _Command:
            cmd_str, _ = cmd.value
            self._commands_long[cmd_str] = cmd
            self._commands_short[cmd_str[0]] = cmd

        self.cmd_action: dict[_Command, Callable[[], None]] = {
            _Command.HELP: self._show_help,
            _Command.CLEAR: console.clear,
        }

    def launch(self) -> None:
        """Launches the REPL.

        This will block until the user signals that the interactive session is
        over or an error occurs.
        """
        cprint("Get help with ':h' or ':help'.")

        while True:
            try:
                user_input = self._get_input()
                if cmd := self._parse_command(user_input):
                    if cmd == _Command.QUIT:
                        break
                    self.cmd_action[cmd]()
                else:
                    self._eval(user_input)
            except _ReplError as exc:
                console.print(f"[red bold]Error:[/] {exc}")

    def _eval(self, script: str) -> None:
        ground_truth = self._interpreter.run(script)
        model_output = "".join(self._model.predict(script))

        output = Table.grid(padding=(0, 1))
        output.add_column()
        output.add_column()

        matched = False

        try:
            parsed = Query.parse(model_output, self._model.tokenizer)
            if steps := parsed.steps:
                output.add_row("[i]Steps[/]", steps)
            output.add_row("[i]Model Result[/]", f"{parsed.result}")
            matched = ground_truth == parsed.result
        except ValueError:
            output.add_row("[i]Model Output[/]", model_output)

        output.add_row("[i]Ground Truth[/]", f"{ground_truth}")
        console.print(output)

        if matched:
            mark = "[green bold]\u2713[/]"
            message = "Correct"
        else:
            mark = "[red bold]\u2718[/]"
            message = "Incorrect"

        console.print(f"{mark} \u2026 {message}")

    def _get_input(self) -> str:
        line = ""
        while len(line) == 0:
            line = console.input(f"{self._prompt} ").rstrip()

        while line[-1] == ";":
            line += console.input(f"{self._prompt_alt} ").rstrip()

        return line.replace(";", "\n")

    def _parse_command(self, line: str) -> _Command | None:
        line = line.strip()
        if line[0] != _COMMAND_CHAR:
            return None

        parts = line[1:].split()
        if len(parts) == 0:
            raise _ReplError(f"No command after the '{_COMMAND_CHAR}'.")

        # The logic here is that if the first if-statement is 'False', because
        # cmd_str is not in the "long commands" dictionary, then check the
        # "short commands" dictionary.
        cmd_str = parts[0]
        if cmd := self._commands_long.get(cmd_str):
            return cmd
        if cmd := self._commands_short.get(cmd_str):
            return cmd
        raise _ReplError(f"Unknown command '{cmd_str}'.")

    def _show_help(self) -> None:
        table = Table()
        table.add_column("Command")
        table.add_column("Description")

        for cmd in _Command:
            cmd_str, desc = cmd.value
            table.add_row(f"{_COMMAND_CHAR}{cmd_str}", desc)

        console.print(table)
