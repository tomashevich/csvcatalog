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


@app.callback(invoke_without_command=True)
def main(
    ctx: Context,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="show version and exit",
        ),
    ] = None,
):
    """a command-line interface tool for managing csv catalogs"""
    # the dbfile command handles its own logic and does not need a storage object
    if ctx.invoked_subcommand == "dbfile":
        return

    settings = config.load_config()
    final_db_path = (
        settings.db_path if settings.db_path else config.get_data_dir() / "catalog.db"
    )

    storage_instance = storage.SqliteStorage(final_db_path)
    ctx.obj = storage_instance
    ctx.call_on_close(storage_instance.close)


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
