from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich.console import Console
from typer import Context

from . import __version__, config, crypto, storage
from .commands import filters as filters_app
from .commands import settings as settings_app
from .commands.delete import DeleteCommand
from .commands.describe import DescribeCommand
from .commands.export import ExportCommand
from .commands.extract import ExtractCommand
from .commands.purge import PurgeCommand
from .commands.search import SearchCommand
from .commands.sql import SqlCommand
from .commands.tables import TablesCommand

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
        password = questionary.password(
            "please enter the database password:", auto_enter=False
        ).ask()
        if not password:
            console.print("[yellow]operation cancelled[/yellow]")
            raise typer.Abort()
        try:
            temp_db_file = crypto.decrypt_file_to_temp(db_path, password)
            storage_path = Path(temp_db_file.name)
        except ValueError as e:
            console.print(f"[red]error: {e}[/red]")
            raise typer.Abort() from e

    storage_instance = storage.SqliteStorage(storage_path)
    ctx.obj = {"storage": storage_instance, "settings": settings}

    def cleanup():
        storage_instance.close()
        if temp_db_file and password and settings.encryption:
            temp_db_file.seek(0)
            plaintext_bytes = temp_db_file.read()
            crypto.encrypt_bytes_to_file(plaintext_bytes, db_path, password)
        if temp_db_file:
            temp_db_file.close()

    ctx.call_on_close(cleanup)


# register command modules that are full typer apps
app.add_typer(settings_app.app, name="settings")
app.add_typer(filters_app.app, name="filters")


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
):
    """extract data from a csv file and load it into a new table"""
    cmd = ExtractCommand(ctx.obj["storage"], ctx.obj["settings"])
    cmd.run(file_path=file_path, encoding=encoding)


@app.command()
def tables(
    ctx: Context,
    description_filter: Annotated[
        str | None,
        typer.Argument(
            help="optional text to filter tables by their description (case-insensitive)"
        ),
    ] = None,
):
    """list all tables in the database"""
    cmd = TablesCommand(ctx.obj["storage"], ctx.obj["settings"])
    cmd.run(description_filter=description_filter)


@app.command()
def delete(
    ctx: Context,
    table_name: Annotated[str, typer.Argument(help="the name of the table to delete")],
):
    """delete a table from the database"""
    cmd = DeleteCommand(ctx.obj["storage"], ctx.obj["settings"])
    cmd.run(table_name=table_name)


@app.command()
def purge(ctx: Context):
    """delete all tables from the database"""
    cmd = PurgeCommand(ctx.obj["storage"], ctx.obj["settings"])
    cmd.run()


@app.command()
def sql(
    ctx: Context,
    query: Annotated[str, typer.Argument(help="the sql query to execute")],
):
    """execute a raw sql query on the database"""
    cmd = SqlCommand(ctx.obj["storage"], ctx.obj["settings"])
    cmd.run(query=query)


@app.command()
def export(
    ctx: Context,
    table_names: Annotated[
        list[str] | None,
        typer.Argument(help="the name of the table(s) to export"),
    ] = None,
):
    """export one or more tables to csv files"""
    cmd = ExportCommand(ctx.obj["storage"], ctx.obj["settings"])
    cmd.run(table_names=table_names)


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
):
    """search for a value in the database"""
    cmd = SearchCommand(ctx.obj["storage"], ctx.obj["settings"])
    cmd.run(value=value, targets=targets)


@app.command()
def describe(
    ctx: Context,
    table_name: Annotated[
        str, typer.Argument(help="the name of the table to describe")
    ],
    description: Annotated[
        str, typer.Argument(help="the description to add to the table")
    ],
):
    """adds or updates a description for a table"""
    cmd = DescribeCommand(ctx.obj["storage"], ctx.obj["settings"])
    cmd.run(table_name=table_name, description=description)
