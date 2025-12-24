from typing import Annotated

import typer
from rich.console import Console

from ..storage import BaseStorage

console = Console()


def describe(
    ctx: typer.Context,
    table_name: Annotated[
        str, typer.Argument(help="the name of the table to describe")
    ],
    description: Annotated[
        str, typer.Argument(help="the description to add to the table")
    ],
):
    """adds or updates a description for a table"""
    storage_instance: BaseStorage = ctx.obj
    try:
        storage_instance.update_description(table_name, description)
        console.print(f"description for table '{table_name}' updated")
    except ValueError as e:
        console.print(f"[red]error: {e}[/red]")
        raise typer.Abort() from e
    except Exception as e:
        console.print(f"[red]an unexpected error occurred: {e}[/red]")
        raise typer.Abort() from e
