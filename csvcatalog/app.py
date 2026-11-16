import sys
from pathlib import Path
from typing import Annotated, cast

import questionary
import typer
from rich.console import Console
from typer import Context

from . import __version__, config, crypto, prompts, storage
from .commands import filters as filters_app
from .commands import settings as settings_app
from .commands import tables
from .commands.base import get_command_context
from .commands.delete import DeleteCommand
from .commands.export import ExportCommand
from .commands.extract import ExtractCommand
from .commands.purge import PurgeCommand
from .commands.search import SearchCommand
from .commands.sql import SqlCommand

app = typer.Typer()
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"csvcatalog version: {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: Context,
    _version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="show version and exit",
        ),
    ] = None,
) -> None:
    """a command-line interface tool for managing csv catalogs"""
    # the settings and filters commands run without db/storage setup
    if ctx.invoked_subcommand in ("settings", "filters"):
        ctx.obj = {"settings": config.load_config()}
        return

    settings = config.load_config()
    db_path = (
        settings.db_path if settings.db_path else config.get_data_dir() / "catalog.db"
    )

    temp_db_file = None
    storage_path = db_path
    password = None
    if settings.encryption:
        password = prompts.ask_text(
            questionary.password(
                "please enter the database password:", auto_enter=False
            )
        )
        if not password:
            console.print("[yellow]operation cancelled[/yellow]")
            raise typer.Abort()
        try:
            temp_db_file = crypto.decrypt_file_to_temp(db_path, password)
            storage_path = Path(temp_db_file.name)
        except ValueError as e:
            console.print(f"[red]error: {e}[/red]")
            raise typer.Abort() from e

    interactive = ctx.invoked_subcommand is None
    storage_instance: storage.BaseStorage | None
    db_error: str | None = None

    if interactive and not settings.encryption and not db_path.exists():
        # the tui will ask for a path instead of silently creating an empty database
        storage_instance = None
    else:
        try:
            storage_instance = storage.SqliteStorage(storage_path)
        except Exception as e:
            if not interactive:
                console.print(f"[red]error opening database: {e}[/red]")
                raise typer.Abort() from e
            storage_instance = None
            db_error = str(e)

    ctx.obj = {"storage": storage_instance, "settings": settings}
    active_storage: storage.BaseStorage | None = storage_instance

    def update_active_storage(value: storage.BaseStorage | None) -> None:
        nonlocal active_storage
        active_storage = value

    def cleanup() -> None:
        if active_storage is not None:
            active_storage.close()
        if temp_db_file and password and settings.encryption:
            _ = temp_db_file.seek(0)
            plaintext_bytes = temp_db_file.read()
            crypto.encrypt_bytes_to_file(plaintext_bytes, db_path, password)
        if temp_db_file:
            temp_db_file.close()

    _ = cast(object, ctx.call_on_close(cleanup))

    if interactive:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            console.print(
                "[yellow]interactive mode requires a terminal; use --help to see commands[/yellow]"
            )
            return
        # imported lazily so the cli stays fast when textual isn't needed
        from .tui import run_tui

        run_tui(
            storage_instance,
            settings,
            db_path,
            db_error=db_error,
            on_storage_change=update_active_storage,
        )


# register command modules that are full typer apps
app.add_typer(settings_app.app, name="settings")
app.add_typer(filters_app.app, name="filters")
app.add_typer(tables.app, name="tables")


# define command entrypoints that call methods on the instantiated classes
@app.command()
def extract(
    ctx: Context,
    file_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    encoding: Annotated[str, typer.Option(help="encoding of the csv file")] = "utf-8",
) -> None:
    """extract data from a csv file and load it into a new table"""
    storage_instance, settings = get_command_context(ctx)
    cmd = ExtractCommand(storage_instance, settings)
    cmd.run(file_path, encoding)


@app.command()
def delete(
    ctx: Context,
    table_name: Annotated[str, typer.Argument(help="the name of the table to delete")],
) -> None:
    """delete a table from the database"""
    storage_instance, settings = get_command_context(ctx)
    cmd = DeleteCommand(storage_instance, settings)
    cmd.run(table_name)


@app.command()
def purge(ctx: Context) -> None:
    """delete all tables from the database"""
    storage_instance, settings = get_command_context(ctx)
    cmd = PurgeCommand(storage_instance, settings)
    cmd.run()


@app.command()
def sql(
    ctx: Context,
    query: Annotated[str, typer.Argument(help="the sql query to execute")],
) -> None:
    """execute a raw sql query on the database"""
    storage_instance, settings = get_command_context(ctx)
    cmd = SqlCommand(storage_instance, settings)
    cmd.run(query)


@app.command()
def export(
    ctx: Context,
    table_names: Annotated[
        list[str] | None,
        typer.Argument(help="the name of the table(s) to export"),
    ] = None,
) -> None:
    """export one or more tables to csv files"""
    storage_instance, settings = get_command_context(ctx)
    cmd = ExportCommand(storage_instance, settings)
    cmd.run(table_names)


@app.command()
def search(
    ctx: Context,
    value: Annotated[str, typer.Argument(help="the value to search for")],
    targets: Annotated[
        list[str] | None,
        typer.Argument(
            help="optional list of targets to search in (e.g., 'table1', 'table2.col1', '*.col2')"
        ),
    ] = None,
) -> None:
    """search for a value in the database"""
    storage_instance, settings = get_command_context(ctx)
    cmd = SearchCommand(storage_instance, settings)
    cmd.run(value, targets)
