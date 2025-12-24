import csv
from typing import Annotated

import questionary
import typer
from questionary import Choice
from rich.console import Console
from rich.markup import escape

from ..storage import BaseStorage

console = Console()


def export(
    ctx: typer.Context,
    table_name: Annotated[str, typer.Argument(help="the name of the table to export")],
):
    """export a table to a csv file"""
    storage_instance: BaseStorage = ctx.obj
    table = storage_instance.get_table(table_name)
    if not table:
        console.print(f"[red]table '{table_name}' not found[/red]")
        raise typer.Abort()

    choices = [Choice(col, checked=True) for col in table.columns]
    columns_to_export = questionary.checkbox(
        f"select columns to export from '{table_name}'",
        choices=choices,
    ).ask()
    if not columns_to_export:
        console.print("[red]no columns selected, aborting[/red]")
        raise typer.Abort()

    # filter loop
    filters: dict[str, str] = {}
    if questionary.confirm("do you want to add filters?", default=False).ask():
        while True:
            choices = [col for col in columns_to_export if col not in filters] + [
                "Done"
            ]
            column_to_filter = questionary.select(
                "select a column to filter (or 'done'):", choices=choices
            ).ask()

            if column_to_filter is None:
                console.print("[red]aborted[/red]")
                raise typer.Abort()
            if column_to_filter == "Done":
                break

            regex_filter = questionary.text(
                f"enter regex filter for '{column_to_filter}':"
            ).ask()
            if regex_filter is None:
                console.print("[red]aborted[/red]")
                raise typer.Abort()
            filters[column_to_filter] = regex_filter

    # ask for unique rows
    export_distinct = questionary.confirm(
        "export only unique rows?", default=False
    ).ask()

    limit_str = questionary.text(
        f"how many rows to export? (all/{table.count})", default="all"
    ).ask()

    if limit_str is None:
        console.print("[red]aborted[/red]")
        raise typer.Abort()

    limit = -1
    if limit_str.lower() != "all":
        try:
            limit = int(limit_str)
            if limit < 0:
                raise ValueError
        except ValueError:
            console.print("[red]invalid input, exporting all rows[/red]")
            limit = -1

    default_filename = f"{table_name}.csv"
    output_filename = questionary.text(
        "enter filename for export:", default=default_filename
    ).ask()
    if not output_filename:
        output_filename = default_filename
    if not output_filename.lower().endswith(".csv"):
        output_filename += ".csv"

    # build query
    select_keyword = "SELECT DISTINCT" if export_distinct else "SELECT"
    columns_str = ", ".join(f'"{c}"' for c in columns_to_export)
    query = f'{select_keyword} {columns_str} FROM "{table_name}"'
    params = []

    if filters:
        console.print("\n[bold]filters applied:[/bold]")
        where_clauses = []
        for col, regex in filters.items():
            console.print(
                f"  - [cyan]{col}[/cyan] -> [magenta]'{escape(regex)}'[/magenta]"
            )
            where_clauses.append(f'"{col}" REGEXP ?')
            params.append(regex)
        query += " WHERE " + " AND ".join(where_clauses)

    if limit != -1:
        query += f" LIMIT {limit}"

    try:
        results = storage_instance.sql(query, params)
        if not results:
            console.print("[yellow]no data found with the given filters[/yellow]")
            raise typer.Abort()

        with open(output_filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(columns_to_export)
            for row in results:
                writer.writerow(row.values())

        console.print(
            f"\n[green]successfully exported {len(results)} rows to '{output_filename}'[/green]"
        )
    except Exception as e:
        console.print(f"[red]error during export: {e}[/red]")
        raise typer.Abort() from e
