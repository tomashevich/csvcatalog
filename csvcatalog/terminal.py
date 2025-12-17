import readline as _FOR_TERMINAL_HISTORY  # for terminal history support # noqa: F401
import shlex
import time
from contextlib import redirect_stdout

from .command import Command
from .registry import CommandRegistry
from .termutils import err_print

# for external module imports
__all__ = ["Terminal", "err_print"]


class Terminal:
    """handles the main command-line interface loop"""

    def __init__(self, registry: CommandRegistry):
        self._registry = registry
        self._should_exit = False
        self._confirm_exit = False
        self._confirm_exit_timeout_s = 2  # 2 seconds timeout for second ctrl+c

    def _parse_command_and_redirection(
        self, raw_cmd: str
    ) -> tuple[list[str], str | None]:
        """parses the raw command string"""
        output_file_path = None
        command_parts = []

        try:
            full_parts = shlex.split(raw_cmd)
        except ValueError as e:
            err_print(f"failed to parse command: {e}")
            return [], None

        if not full_parts:
            return [], None

        redirect_index = -1
        for i, part in enumerate(full_parts):
            if part == ">":
                redirect_index = i
                break

        if redirect_index != -1:
            command_parts = full_parts[:redirect_index]
            if redirect_index + 1 < len(full_parts):
                output_file_path = full_parts[redirect_index + 1]
            else:
                err_print("redirection target file path missing after '>'")
                return [], None  # Indicate failure by returning empty command_parts
        else:
            command_parts = full_parts

        return command_parts, output_file_path

    def _execute_command_with_redirection(
        self, command: Command, args: list[str], output_file_path: str
    ) -> None:
        """executes cmd and stdout to file `cmd > file.txt`"""
        try:
            with open(output_file_path, "w") as f:
                with redirect_stdout(f):
                    command.execute(*args)
            print(f"Output redirected to '{output_file_path}'")
        except OSError as e:
            err_print(f"failed to write to file '{output_file_path}': {e}")
        except Exception as e:
            err_print(f"error during command execution: {e}")

    def _execute(self, raw_cmd: str) -> None:
        """executes a raw command string"""
        if not raw_cmd:
            return

        command_parts, output_file_path = self._parse_command_and_redirection(raw_cmd)

        if (
            not command_parts
        ):  # This covers cases where parsing failed or resulted in no command
            return

        name, *args = command_parts
        command = self._registry.get(name)

        if not command:  # Moved this check up to flatten
            err_print(f"unknown command '{name}'")
            return

        if output_file_path:
            self._execute_command_with_redirection(command, args, output_file_path)
        else:
            command.execute(*args)

    def run(self) -> None:
        """runs the main terminal loop, handling user input and command execution"""
        while not self._should_exit:
            try:
                # if confirm_exit is true, check if timeout has passed
                if (
                    self._confirm_exit
                    and time.time() - self._confirm_time > self._confirm_exit_timeout_s
                ):
                    self._confirm_exit = False
                    print("exit cancelled")

                raw_cmd = input("> ")
                self._execute(raw_cmd)
                self._confirm_exit = False
            except (KeyboardInterrupt, EOFError):
                if self._confirm_exit:
                    self._should_exit = True
                else:
                    self._confirm_exit = True
                    self._confirm_time = (
                        time.time()
                    )  # set the time when first ctrl+c was pressed
                    print("\n(press ctrl+c again to exit)")
        print("\nbye")
