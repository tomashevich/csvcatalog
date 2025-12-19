from typing import Annotated

import questionary
import typer
from rich.console import Console

from ..storage import Storage

console = Console()

def delete(
    ctx: typer.Context,
    table_name: Annotated[str, typer.Argument(help="the name of the table to delete")],
):
    """delete a table"""
    storage_instance: Storage = ctx.obj
    if not questionary.confirm(
        f"are you sure you want to delete table '{table_name}'?"
    ).unsafe_ask():
        console.print("[red]aborted[/red]")
        raise typer.Abort()

    try:
        storage_instance.delete_table(table_name)
        console.print(f"[green]table '{table_name}' deleted successfully[/green]")
    except Exception as e:
        console.print(f"[red]error deleting table: {e}[/red]")
        raise typer.Abort()
