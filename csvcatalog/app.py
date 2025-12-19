from pathlib import Path
from typing import Annotated

import typer
from platformdirs import user_data_dir
from rich.console import Console
from typer import Context

from . import __version__, storage
from .commands.delete import delete
from .commands.export import export
from .commands.extract import extract
from .commands.purge import purge
from .commands.search import search
from .commands.sql import sql
from .commands.tables import tables

app = typer.Typer()
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"csvcatalog version: {__version__}")
        raise typer.Exit()


def get_db_path(db_path: str | None = None) -> Path:
    if db_path:
        return Path(db_path)

    data_dir = Path(user_data_dir("csvcatalog", "tomashevich"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "catalog.db"


@app.callback()
def main(
    ctx: Context,
    db_path: Annotated[
        str | None,
        typer.Option(
            help="path to the database file",
        ),
    ] = None,
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
):
    """a command-line interface tool for managing csv catalogs"""
    ctx.obj = storage.Storage(get_db_path(db_path))


app.command()(extract)
app.command()(tables)
app.command()(delete)
app.command()(purge)
app.command()(sql)
app.command()(export)
app.command()(search)


if __name__ == "__main__":
    app()
