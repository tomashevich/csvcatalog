import questionary
import typer
from rich.console import Console

from ..storage import BaseStorage

console = Console()


def purge(ctx: typer.Context):
    """clear the entire database"""
    storage_instance: BaseStorage = ctx.obj

    confirmed = questionary.confirm(
        "are you sure you want to clear the entire database?"
    ).ask()

    if not confirmed:
        console.print("[red]aborted[/red]")
        raise typer.Abort()

    try:
        storage_instance.purge_database()
        console.print("[green]database purged successfully[/green]")
    except Exception as e:
        console.print(f"[red]error purging database: {e}[/red]")
        raise typer.Abort()