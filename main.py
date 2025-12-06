import os

from src.cmd.command import Command
from src.cmd.terminal import Terminal


def main():
    commands = [
        Command(
            "help",
            lambda _: print(
                f"Available commands: \n   {('\n   '.join(str(cmd) for cmd in commands))}"
            ),
        ),
        Command("exit", lambda _: exit(0)),
        Command("clear", lambda _: os.system("clear")),
    ]

    terminal = Terminal()

    for command in commands:
        terminal.register_command(command)

    terminal.run()


if __name__ == "__main__":
    main()
