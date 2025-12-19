import csv
from typing import Annotated

import questionary
import typer
from rich.console import Console

from ..storage import Storage

console = Console()

def export(
    ctx: typer.Context,
    table_name: Annotated[str, typer.Argument(help="the name of the table to export")],
):
    """export a table to a csv file"""
    storage_instance: Storage = ctx.obj
    table = storage_instance.get_table(table_name)
    if not table:
        console.print(f"[red]table '{table_name}' not found[/red]")
        raise typer.Abort()

    columns_to_export = questionary.checkbox(
        f"select columns to export from '{table_name}'",
        choices=table.columns,
    ).unsafe_ask()
    if not columns_to_export:
        console.print("[red]no columns selected, aborting[/red]")
        raise typer.Abort()

    limit_str = questionary.text(
        f"how many rows to export? (all/{table.count})", default="all"
    ).unsafe_ask()
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
    ).unsafe_ask()
    if not output_filename:
        output_filename = default_filename
    if not output_filename.lower().endswith(".csv"):
        output_filename += ".csv"

    columns_str = ", ".join(f'"{c}"' for c in columns_to_export)
    query = f'SELECT {columns_str} FROM "{table_name}"'
    if limit != -1:
        query += f" LIMIT {limit}"

    try:
        results = storage_instance.sql(query)
        with open(output_filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(columns_to_export)
            for row in results:
                writer.writerow(row.values())

        console.print(
            f"[green]successfully exported to '{output_filename}'[/green]"
        )
    except Exception as e:
        console.print(f"[red]error during export: {e}[/red]")
        raise typer.Abort()
