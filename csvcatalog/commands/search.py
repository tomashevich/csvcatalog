import time
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .base import CommandBase

console = Console()


class SearchCommand(CommandBase):
    def execute(
        self,
        value: Annotated[str, typer.Argument(help="the value to search for")],
        targets: Annotated[
            list[str] | None,
            typer.Argument(
                help="optional list of targets to search in (e.g., 'table1', 'table2.col1', '*.col2')"
            ),
        ] = None,
    ):
        """search for a value in specified tables/columns or globally"""
        targets = targets if targets is not None else []
        start_time = time.time()
        console.print(f"searching for '{value}'...")

        results = self.storage.search(value, targets)
        duration = time.time() - start_time

        if not results:
            console.print("no matches found")
            return

        total_matches = sum(len(rows) for rows in results.values())
        console.print(
            f"found {total_matches} total match(es) in {duration:.4f} seconds"
        )

        for table_name, rows in results.items():
            console.print(f"\nfound {len(rows)} match(es) in table '{table_name}':")
            rich_table = Table(show_header=True, header_style="bold magenta")
            if not rows:
                continue
            for col in rows[0].keys():
                rich_table.add_column(col)
            for row in rows:
                rich_table.add_row(*(str(v) for v in row.values()))
            console.print(rich_table)
