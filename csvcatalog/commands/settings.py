from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich.console import Console
from rich.table import Table
from typer import Context

from .. import config, crypto

app = typer.Typer(invoke_without_command=True)
console = Console()


def _show_settings():
    """loads and displays current settings"""
    settings = config.load_config()
    table = Table("setting", "value")
    db_path_str = (
        str(settings.db_path) if settings.db_path else "[yellow]not set[/yellow]"
    )
    encryption_str = "[green]on[/green]" if settings.encryption else "[red]off[/red]"
    table.add_row("db_path", db_path_str)
    table.add_row("encryption", encryption_str)
    console.print(table)


@app.callback(invoke_without_command=True)
def main(ctx: Context):
    """manage application settings"""
    if ctx.invoked_subcommand is None:
        _show_settings()


@app.command()
def show():
    """show current settings"""
    _show_settings()


@app.command()
def dbfile(
    ctx: typer.Context,
    db_path: Annotated[Path, typer.Argument(help="path to the database file")],
):
    """set the path to the database file"""
    settings = config.load_config()
    settings.db_path = db_path
    config.save_config(settings)
    console.print(f"database path set to: {db_path.resolve()}")


@app.command()
def encryption(
    ctx: typer.Context,
    enable: Annotated[bool, typer.Argument(help="enable or disable encryption")],
):
    """enable or disable database encryption"""
    settings = config.load_config()
    if settings.encryption == enable:
        status = "enabled" if enable else "disabled"
        console.print(f"encryption is already {status}")
        return

    db_path = settings.db_path
    if not db_path:
        console.print(
            "[red]error: database path is not set, use 'settings dbfile' first[/red]"
        )
        raise typer.Abort()

    if not db_path.exists():
        console.print(
            f"database file '{db_path}' does not exist yet, saving encryption setting"
        )
        settings.encryption = enable
        config.save_config(settings)
        status = "enabled" if enable else "disabled"
        console.print(f"encryption {status}, a password will be required on next use")
        return

    password = questionary.password("please enter the password for the database:").ask()
    if not password:
        console.print("[yellow]operation cancelled[/yellow]")
        raise typer.Abort()

    try:
        if enable:
            console.print(f"encrypting '{db_path}'...")
            crypto.encrypt_file(db_path, password)
            console.print("[green]encryption successful[/green]")
        else:
            console.print(f"decrypting '{db_path}'...")
            crypto.decrypt_file(db_path, password)
            console.print("[green]decryption successful[/green]")

        settings.encryption = enable
        config.save_config(settings)

    except ValueError as e:
        console.print(f"[red]error: {e}[/red]")
        raise typer.Abort() from e
