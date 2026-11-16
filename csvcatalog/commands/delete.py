from typing import override

import questionary
import typer
from rich.console import Console

from ..prompts import ask_bool
from .base import CommandBase

console = Console()


class DeleteCommand(CommandBase[[list[str]]]):
    @override
    def execute(
        self,
        table_names: list[str],
    ) -> None:
        """delete one or more tables"""
        existing = [
            table_name
            for table_name in table_names
            if self.storage.get_table(table_name) is not None
        ]
        for table_name in table_names:
            if table_name not in existing:
                console.print(
                    f"[yellow]table '{table_name}' not found, skipping[/yellow]"
                )
        if not existing:
            raise typer.Abort()

        if len(existing) == 1:
            question = f"are you sure you want to delete table '{existing[0]}'?"
        else:
            question = (
                f"are you sure you want to delete {len(existing)} tables: "
                f"{', '.join(existing)}?"
            )
        if not ask_bool(questionary.confirm(question, default=False)):
            raise typer.Abort()

        for table_name in existing:
            self.storage.delete_table(table_name)
            console.print(f"[green]table '{table_name}' deleted successfully[/green]")


__all__ = ["DeleteCommand"]
