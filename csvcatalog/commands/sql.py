from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .base import CommandBase

console = Console()


class SqlCommand(CommandBase):
    def execute(
        self,
        query: Annotated[str, typer.Argument(help="the sql query to execute")],
    ):
        """execute sql command"""
        results = self.storage.sql(query)
        if not results:
            console.print("[yellow]query returned no results[/yellow]")
            return

        table = Table(show_header=True, header_style="bold magenta")
        for col in results[0].keys():
            table.add_column(col)
        for row in results:
            table.add_row(*(str(v) for v in row.values()))
        console.print(table)
