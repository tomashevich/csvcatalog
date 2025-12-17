import readline as _FOR_TERMINAL_HISTORY  # for terminal history support # noqa: F401
import shlex
import time

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

    def _execute(self, raw_cmd: str) -> None:
        """executes a raw command string"""
        if not raw_cmd:
            return

        try:
            parts = shlex.split(raw_cmd)
        except ValueError as e:
            err_print(f"failed to parse command: {e}")
            return

        if not parts:
            return

        name, *args = parts
        command = self._registry.get(name)

        if command:
            command.execute(*args)
        else:
            err_print(f"unknown command '{name}'")

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
