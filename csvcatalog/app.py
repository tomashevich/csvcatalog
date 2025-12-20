from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from typer import Context

from . import __version__, config, storage
from .commands.dbfile import dbfile
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


@app.callback()
def main(
    ctx: Context,
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
):
    """a command-line interface tool for managing csv catalogs"""
    # the dbfile command handles its own logic and does not need a storage object
    if ctx.invoked_subcommand == "dbfile":
        return

    settings = config.load_config()
    if "db_path" in settings:
        final_db_path = Path(settings["db_path"])
    else:
        final_db_path = config.get_data_dir() / "catalog.db"

    ctx.obj = storage.SqliteStorage(final_db_path)


app.command()(extract)
app.command()(tables)
app.command()(delete)
app.command()(purge)
app.command()(sql)
app.command()(export)
app.command()(search)
app.command()(dbfile)


if __name__ == "__main__":
    app()
