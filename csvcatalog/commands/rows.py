import math
from typing import override

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from .base import CommandBase

console = Console()


class RowsCommand(
    CommandBase[[str, int, int, str | None, list[str] | None, str | None, bool]]
):
    @override
    def execute(
        self,
        table_name: str,
        limit: int,
        page: int,
        search: str | None,
        search_columns: list[str] | None,
        sort_column: str | None,
        sort_desc: bool,
    ) -> None:
        """show one page of rows with optional search and sorting"""
        table = self.storage.get_table(table_name)
        if table is None:
            console.print(f"[red]error: table '{table_name}' not found[/red]")
            raise typer.Abort()

        if search_columns:
            invalid = [
                column for column in search_columns if column not in table.columns
            ]
            if invalid:
                console.print(
                    f"[red]error: unknown search columns: {escape(', '.join(invalid))}[/red]"
                )
                raise typer.Abort()
        if sort_column and sort_column not in table.columns:
            console.print(
                f"[red]error: unknown sort column: {escape(sort_column)}[/red]"
            )
            raise typer.Abort()

        limit = max(1, limit)
        page = max(1, page)
        offset = (page - 1) * limit
        rows, total = self.storage.get_rows(
            table_name,
            offset=offset,
            limit=limit,
            search=search,
            search_columns=search_columns,
            sort_column=sort_column,
            sort_desc=sort_desc,
        )
        pages = max(1, math.ceil(total / limit))
        if page > pages and total:
            page = pages
            offset = (page - 1) * limit
            rows, total = self.storage.get_rows(
                table_name,
                offset=offset,
                limit=limit,
                search=search,
                search_columns=search_columns,
                sort_column=sort_column,
                sort_desc=sort_desc,
            )

        start = offset + 1 if total else 0
        end = min(offset + len(rows), total)
        summary = f"rows {start:,}–{end:,} of {total:,} · page {page:,} of {pages:,}"
        if search:
            summary += f" · matching “{escape(search)}”"
            if search_columns and len(search_columns) < len(table.columns):
                summary += f" in {len(search_columns)} column(s)"
        console.print(summary)

        if not rows:
            console.print("[yellow]no rows found[/yellow]")
            return

        rich_table = Table(show_header=True, header_style="bold magenta")
        for column in table.columns:
            rich_table.add_column(column)
        for row in rows:
            rich_table.add_row(
                *[_display_value(row.get(column)) for column in table.columns]
            )
        console.print(rich_table)


def _display_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


__all__ = ["RowsCommand"]
