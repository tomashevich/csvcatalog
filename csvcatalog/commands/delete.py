from typing import Annotated

import questionary
import typer
from rich.console import Console

from .base import CommandBase

console = Console()


class DeleteCommand(CommandBase):
    def execute(
        self,
        table_name: Annotated[
            str, typer.Argument(help="the name of the table to delete")
        ],
    ):
        """delete a table"""
        # check if table exists first
        if not self.storage.get_table(table_name):
            console.print(f"[red]error: table '{table_name}' not found[/red]")
            raise typer.Abort()

        if not questionary.confirm(
            f"are you sure you want to delete table '{table_name}'?",
            default=False,
        ).ask():
            raise typer.Abort()

        self.storage.delete_table(table_name)
        console.print(f"[green]table '{table_name}' deleted successfully[/green]")
