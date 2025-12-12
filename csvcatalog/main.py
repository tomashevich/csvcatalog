import os
import sys

from .file import File
from .registry import registry
from .storage import Storage
from .terminal import Terminal


def main():
    # Define and register general commands
    def _help() -> None:
        print("Available commands:")
        for cmd in registry.all_commands():
            print(f"  {cmd}")

    def _exit() -> None:
        sys.exit(0)

    def _clear() -> None:
        os.system("cls" if os.name == "nt" else "clear")

    registry.register("help", _help, description="Show all available commands.")
    registry.register(
        "exit", _exit, description="Exit the application.", aliases=["quit"]
    )
    registry.register("clear", _clear, description="Clear the screen.", aliases=["cls"])

    # Initialize modules to register their commands
    storage = Storage("catalog.db")
    File(storage)

    # Run the terminal interface
    terminal = Terminal(registry)
    terminal.run()


if __name__ == "__main__":
    main()
