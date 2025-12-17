import argparse
import os
import subprocess
import sys

from platformdirs import user_data_dir

from .registry import registry
from .storage import Storage
from .terminal import Terminal, err_print
from .wizard import ExtractionWizard


def main():
    """main entry point for the csv catalog cli tool"""
    parser = argparse.ArgumentParser(
        description="a command-line interface tool for managing csv catalogs"
    )
    parser.add_argument(
        "--db",
        type=str,
        help="path to the database file",
        default=None,
    )
    args = parser.parse_args()

    db_path = args.db
    if db_path is None:
        data_dir = user_data_dir("csvcatalog", "tomashevich")
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "catalog.db")

    storage = Storage(db_path)

    # define and register general commands
    def _help() -> None:
        print("available commands:")
        for cmd in registry.all_commands():
            print(f"  {cmd}")

    def _exit() -> None:
        sys.exit(0)

    def _clear() -> None:
        subprocess.run("cls" if os.name == "nt" else "clear", shell=True)

    def _system(*cmd: str) -> None:
        subprocess.run(" ".join(cmd), shell=True)

    def _run_extraction_wizard(file_path: str) -> None:
        try:
            wizard = ExtractionWizard(storage, file_path)
            wizard.run()
        except (FileNotFoundError, IsADirectoryError) as e:
            err_print(str(e))
        except Exception as e:
            err_print(f"an unexpected error occurred: {e}")

    registry.register(
        name="help", handler=_help, description="show all available commands"
    )
    registry.register(
        name="exit", handler=_exit, description="exit the application", aliases=["quit"]
    )
    registry.register(
        name="clear", handler=_clear, description="clear the screen", aliases=["cls"]
    )
    registry.register(
        name="system", handler=_system, description="run a system command"
    )
    registry.register(
        name="extract",
        handler=_run_extraction_wizard,
        description="run interactive wizard to extract data from a csv file",
        example="extract data.csv",
        aliases=["parse"],
    )

    # run the terminal interface
    terminal = Terminal(registry)
    terminal.run()


if __name__ == "__main__":
    main()
