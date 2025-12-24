from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ..storage import BaseStorage

console = Console()


def sql(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="The SQL query to execute")],
):
    """execute sql command"""
    storage_instance: BaseStorage = ctx.obj
    try:
        results = storage_instance.sql(query)
        if not results:
            console.print("[yellow]query returned no results[/yellow]")
            return

        table = Table(show_header=True, header_style="bold magenta")
        for col in results[0].keys():
            table.add_column(col)
        for row in results:
            table.add_row(*(str(v) for v in row.values()))
        console.print(table)

    except Exception as e:
        console.print(f"[red]error executing sql: {e}[/red]")
        raise typer.Abort() from e
