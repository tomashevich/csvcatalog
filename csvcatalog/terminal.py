import readline as _FOR_TERMINAL_HISTORY  # noqa: F401
import shlex
import time

from .registry import CommandRegistry


class Terminal:
    def __init__(self, registry: CommandRegistry):
        self._registry = registry
        self._should_exit = False
        self._confirm_exit = False

    def _execute(self, raw_cmd: str) -> None:
        if not raw_cmd:
            return

        try:
            parts = shlex.split(raw_cmd)
        except ValueError as e:
            print(f"error: failed to parse command: {e}")
            return

        if not parts:
            return

        name, *args = parts
        command = self._registry.get(name)

        if command:
            command.execute(*args)
        else:
            print(f"error: unknown command '{name}'")

    def run(self) -> None:
        while not self._should_exit:
            try:
                raw_cmd = input("> ")
                self._execute(raw_cmd)
                self._confirm_exit = False
            except (KeyboardInterrupt, EOFError):
                if self._confirm_exit:
                    self._should_exit = True
                else:
                    self._confirm_exit = True
                    print("\n(Press Ctrl+C again to exit)")
                    self.confirm_time = time.time()
        print("\nBye!")
