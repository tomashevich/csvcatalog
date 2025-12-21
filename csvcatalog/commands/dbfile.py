from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .. import config

console = Console()


def dbfile(
    new_path: Annotated[
        Path | None,
        typer.Argument(
            help="Optional: new path to set as the default database file",
            resolve_path=True,
        ),
    ] = None,
):
    """display or update the default database file path"""
    settings = config.load_config()

    if new_path:
        settings.db_path = new_path
        config.save_config(settings)
        console.print(f"[green]default database path updated to: {new_path}[/green]")
        return

    if settings.db_path:
        console.print(f"current database path: {settings.db_path}")
        return

    default_path = config.get_data_dir() / "catalog.db"
    console.print(f"no default path set - using default: {default_path}")
