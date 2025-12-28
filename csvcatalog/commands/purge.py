import questionary
import typer
from rich.console import Console

from .base import CommandBase

console = Console()


class PurgeCommand(CommandBase):
    def execute(
        self,
    ):
        """clear the entire database"""
        if not questionary.confirm(
            "are you sure you want to clear the entire database?",
            default=False,
        ).ask():
            console.print("[red]aborted[/red]")
            raise typer.Abort()

        self.storage.purge_database()
        console.print("[green]database purged successfully[/green]")
