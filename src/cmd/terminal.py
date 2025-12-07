import readline as _FOR_TERMINAL_HISTORY  # noqa: F401
import shlex
import time

from .command import Command


class Terminal:
    def __init__(self):
        self.commands: dict[str, Command] = {}
        self.confirm_time = time.time()

    def register_command(self, command: Command) -> None:
        for name in command.aliases:
            self.commands[name] = command

        self.commands[command.name] = command

    def run(self) -> None:
        while True:
            try:
                raw_cmd = input("$ ")
                if not raw_cmd:
                    continue

                cmd = shlex.split(raw_cmd)
                if not cmd:
                    continue

                name = cmd[0]
                args = cmd[1:]

                if self.commands.get(name, 0):
                    self.commands[name].execute(*args)

                else:
                    print("unknown command")

            except (KeyboardInterrupt, EOFError):
                if time.time() - self.confirm_time > 1:
                    print("confirm exit pressing ctrl+c second time")
                    self.confirm_time = time.time()
                    continue

                break
            except ValueError as e:
                print(f"cant parse command: {e}")
