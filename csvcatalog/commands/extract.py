import csv
from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich.console import Console
from rich.table import Table

from ..storage import BaseStorage

console = Console()

# Constants for batch processing
BATCH_SIZE = 10_000
FILE_SIZE_THRESHOLD_MB = 50


def extract(
    ctx: typer.Context,
    file_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
        ),
    ],
):
    """run interactive wizard to extract data from a csv file"""
    console.print(f"starting extraction for '{file_path}'")
    storage_instance: BaseStorage = ctx.obj

    # set separator
    separator = questionary.text("enter csv separator:", default=",").unsafe_ask()
    if not separator:
        console.print("[red]aborted[/red]")
        raise typer.Abort()

    # define columns and preview using csv module
    try:
        with file_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f, delimiter=separator)
            csv_headers = next(reader)
            preview_rows = [row for i, row in enumerate(reader) if i < 5]
    except StopIteration:
        console.print("[red]file appears to be empty or has only a header[/red]")
        raise typer.Abort()
    except Exception as e:
        console.print(f"[red]could not read file: {e}[/red]")
        raise typer.Abort()

    console.print("\n[bold]raw preview:[/bold]")
    console.print(separator.join(csv_headers))
    for row in preview_rows:
        console.print(separator.join(row))

    console.print("\n[bold]define database column names for each csv header[/bold]")
    console.print("press enter to accept the default name")

    column_map = {}
    for header in csv_headers:
        column_name = questionary.text(
            f"  csv header '{header}' -> column name:", default=header
        ).unsafe_ask()
        if not column_name:
            console.print("[red]aborted[/red]")
            raise typer.Abort()
        column_map[header] = column_name

    # select columns
    columns_to_import = questionary.checkbox(
        "select the columns you want to import",
        choices=list(column_map.values()),
    ).unsafe_ask()
    if not columns_to_import:
        console.print("[red]no columns selected, aborting[/red]")
        raise typer.Abort()

    # table name
    default_table_name = file_path.stem.strip()
    table_name = questionary.text(
        "enter table name:", default=default_table_name
    ).unsafe_ask()
    if not table_name:
        console.print("[red]aborted[/red]")
        raise typer.Abort()

    # preview data
    console.print("\n[bold]preview of data to be imported:[/bold]")
    header_to_idx = {header: i for i, header in enumerate(csv_headers)}
    data_to_preview = []
    for line in preview_rows:
        row_data = {}
        for csv_header, column_name in column_map.items():
            if column_name in columns_to_import:
                idx = header_to_idx.get(csv_header)
                if idx is not None and idx < len(line):
                    row_data[column_name] = line[idx]
        if row_data:
            data_to_preview.append(row_data)

    if data_to_preview:
        table = Table(show_header=True, header_style="bold magenta")
        for col in columns_to_import:
            table.add_column(col)
        for row in data_to_preview:
            table.add_row(*(row.get(col, "") for col in columns_to_import))
        console.print(table)

    # summary
    console.print("\n[bold]summary[/bold]")
    console.print(f"  file:       {file_path}")
    console.print(f"  table:      {table_name}")
    console.print(f"  separator:  '{separator}'")
    console.print(f"  columns:    {', '.join(columns_to_import)}")
    console.print("[bold]column mapping:[/bold]")
    for csv_h, db_f in column_map.items():
        if db_f in columns_to_import:
            console.print(f"  - '{csv_h}' -> '{db_f}'")

    if not questionary.confirm("proceed with extraction?").unsafe_ask():
        console.print("[red]aborted[/red]")
        raise typer.Abort()

    # extraction
    try:
        console.print("starting extraction...")
        storage_instance.create_table(table_name, columns_to_import)

        with file_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f, delimiter=separator)
            next(reader)  # skip header

            batch = []
            total_saved = 0
            for _, row_parts in enumerate(reader):
                if not row_parts:
                    continue
                row_data = {}
                for csv_header, column_name in column_map.items():
                    if column_name in columns_to_import:
                        idx = header_to_idx.get(csv_header)
                        if idx is not None and idx < len(row_parts):
                            row_data[column_name] = row_parts[idx]
                if row_data:
                    batch.append(row_data)

                if len(batch) >= BATCH_SIZE:
                    storage_instance.save(table_name, batch)
                    total_saved += len(batch)
                    console.print(f"  ... saved {total_saved} rows")
                    batch.clear()

            if batch:
                storage_instance.save(table_name, batch)
                total_saved += len(batch)

        console.print(f"[green]extraction complete. saved {total_saved} rows.[/green]")

    except Exception as e:
        console.print(f"[red]an error occurred during extraction: {e}[/red]")
        raise typer.Abort()
