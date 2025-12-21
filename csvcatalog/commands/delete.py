from typing import Annotated

import questionary
import typer
from rich.console import Console

from ..storage import BaseStorage

console = Console()


def delete(
    ctx: typer.Context,
    table_name: Annotated[str, typer.Argument(help="the name of the table to delete")],
):
    """delete a table"""
    storage_instance: BaseStorage = ctx.obj
    
    confirmed = questionary.confirm(
        f"are you sure you want to delete table '{table_name}'?"
    ).ask()

    if not confirmed:
        console.print("[red]aborted[/red]")
        raise typer.Abort()

    try:
        storage_instance.delete_table(table_name)
        console.print(f"[green]table '{table_name}' deleted successfully[/green]")
    except Exception as e:
        console.print(f"[red]error deleting table: {e}[/red]")
        raise typer.Abort()