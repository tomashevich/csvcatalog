from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich.console import Console
from typer import Context

from . import __version__, config, crypto, storage
from .commands import settings as settings_app
from .commands.delete import delete
from .commands.describe import describe
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


def _setup_encrypted_storage(db_path: Path):
    """handles the logic of setting up storage for an encrypted database"""
    password = questionary.password("please enter the database password:").ask()
    if not password:
        console.print("[yellow]operation cancelled[/yellow]")
        raise typer.Abort()

    try:
        temp_db_file = crypto.decrypt_file_to_temp(db_path, password)
        storage_path = Path(temp_db_file.name)
        return storage_path, password, temp_db_file
    except ValueError as e:
        console.print(f"[red]error: {e}[/red]")
        raise typer.Abort() from e


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
    if ctx.invoked_subcommand == "settings":
        return

    settings = config.load_config()
    db_path = (
        settings.db_path if settings.db_path else config.get_data_dir() / "catalog.db"
    )

    temp_db_file = None
    storage_path = db_path
    password = None
    if settings.encryption:
        storage_path, password, temp_db_file = _setup_encrypted_storage(db_path)

    storage_instance = storage.SqliteStorage(storage_path)
    ctx.obj = storage_instance

    # closes db connection, re-encrypts and delete temp file
    def cleanup():
        storage_instance.close()

        if temp_db_file and password and settings.encryption:
            temp_db_file.seek(0)
            plaintext_bytes = temp_db_file.read()
            crypto.encrypt_bytes_to_file(plaintext_bytes, db_path, password)

        if temp_db_file:
            temp_db_file.close()

    ctx.call_on_close(cleanup)


app.add_typer(settings_app.app, name="settings")
app.command()(extract)
app.command()(tables)
app.command()(delete)
app.command()(purge)
app.command()(sql)
app.command()(export)
app.command()(search)
app.command()(describe)


if __name__ == "__main__":
    app()
