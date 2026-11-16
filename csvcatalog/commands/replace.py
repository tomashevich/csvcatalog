from typing import override

import questionary
import typer
from rich.console import Console
from rich.markup import escape

from ..prompts import ask_bool
from .base import CommandBase

console = Console()


class ReplaceCommand(CommandBase[[str, str, str, list[str] | None, bool]]):
    @override
    def execute(
        self,
        table_name: str,
        search_value: str,
        replacement: str,
        columns: list[str] | None,
        yes: bool,
    ) -> None:
        """replace every case-insensitive occurrence in the selected columns"""
        table = self.storage.get_table(table_name)
        if table is None:
            console.print(f"[red]error: table '{table_name}' not found[/red]")
            raise typer.Abort()

        if not search_value:
            console.print("[red]error: search text cannot be empty[/red]")
            raise typer.Abort()

        selected_columns = columns or list(table.columns)
        invalid = [column for column in selected_columns if column not in table.columns]
        if invalid:
            console.print(
                f"[red]error: unknown columns: {escape(', '.join(invalid))}[/red]"
            )
            raise typer.Abort()
        if not selected_columns:
            console.print("[red]error: no columns selected[/red]")
            raise typer.Abort()

        if not yes:
            confirmed = ask_bool(
                questionary.confirm(
                    f"replace all matches of '{search_value}' with '{replacement}' in {', '.join(selected_columns)} of table '{table_name}'?",
                    default=False,
                )
            )
            if not confirmed:
                console.print("[red]aborted[/red]")
                raise typer.Abort()

        rows, occurrences = self.storage.replace_in_columns(
            table_name,
            selected_columns,
            search_value,
            replacement,
        )
        if occurrences == 0:
            console.print("[yellow]no matches found[/yellow]")
            return
        console.print(
            f"[green]replaced {occurrences} occurrence(s) in {rows} row(s)[/green]"
        )


__all__ = ["ReplaceCommand"]
