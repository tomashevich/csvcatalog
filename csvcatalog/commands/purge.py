from typing import override

import questionary
import typer
from rich.console import Console

from ..prompts import ask_bool
from .base import CommandBase

console = Console()


class PurgeCommand(CommandBase[[]]):
    @override
    def execute(self) -> None:
        """clear the entire database"""
        if not ask_bool(
            questionary.confirm(
                "are you sure you want to clear the entire database?",
                default=False,
            )
        ):
            console.print("[red]aborted[/red]")
            raise typer.Abort()

        self.storage.purge_database()
        console.print("[green]database purged successfully[/green]")
