import shlex

from .command import Command


class Terminal:
    def __init__(self):
        self.commands: dict[str, Command] = {}

    def register_command(self, command: Command) -> None:
        self.commands[command.name] = command

    def run(self) -> None:
        while True:
            raw_cmd = input("$ ")
            if not raw_cmd:
                continue

            try:
                cmd = shlex.split(raw_cmd)
                if not cmd:
                    continue

                name = cmd[0]
                args = cmd[1:]

                if self.commands.get(name, 0):
                    self.commands[name].execute(*args)

                else:
                    print("unknown command")

            except ValueError as e:
                print(f"cant parse command: {e}")
