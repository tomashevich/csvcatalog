import os

from src.cmd.command import Command
from src.cmd.terminal import Terminal
from src.extractor.extractor import Extractor


def main():
    ex = Extractor()
    terminal = Terminal()

    # Register all commands
    commands = [
        Command(
            "help",
            lambda: print(
                f"Available commands: \n   {('\n   '.join(str(cmd) for cmd in commands))}"
            ),
        ),
        Command("exit", lambda: exit(0)),
        Command("clear", lambda: os.system("clear"), aliases=["cls", "c"]),
        Command(
            "system",
            lambda *cmd: os.system(" ".join(cmd)),
            description="execute a system command",
            example="system ls",
        ),
    ]
    commands.extend(ex.commands)

    for command in commands:
        terminal.register_command(command)

    terminal.run()


if __name__ == "__main__":
    main()
