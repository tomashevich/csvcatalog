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
        if not questionary.confirm(
            f"are you sure you want to delete table '{table_name}'?",
            default=False,
        ).ask():
            console.print("[red]aborted[/red]")
            raise typer.Abort()

        self.storage.delete_table(table_name)
        console.print(f"[green]table '{table_name}' deleted successfully[/green]")
