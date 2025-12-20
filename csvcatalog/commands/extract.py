from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich.console import Console
from rich.table import Table

from ..storage import BaseStorage

console = Console()


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

    # initial preview
    try:
        with file_path.open("r", encoding="utf-8-sig") as f:
            raw_lines = [line.strip() for i, line in enumerate(f) if i < 5]
        if not raw_lines:
            console.print("[red]file appears to be empty[/red]")
            raise typer.Abort()
        console.print("\n[bold]raw preview:[/bold]")
        for line in raw_lines:
            console.print(line)
    except Exception as e:
        console.print(f"[red]could not read file: {e}[/red]")
        raise typer.Abort()

    # set separator
    separator = questionary.text("enter csv separator:", default=",").unsafe_ask()
    if not separator:
        console.print("[red]aborted[/red]")
        raise typer.Abort()

    # define columns
    try:
        with file_path.open("r", encoding="utf-8-sig") as f:
            csv_headers = f.readline().strip().split(separator)
    except Exception as e:
        console.print(f"[red]could not read file: {e}[/red]")
        raise typer.Abort()

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
    try:
        with file_path.open("r", encoding="utf-8-sig") as f:
            lines = [line.strip().split(separator) for i, line in enumerate(f) if i < 6]

        if len(lines) > 1:
            header_to_idx = {header: i for i, header in enumerate(csv_headers)}
            data_to_preview = []
            for line in lines[1:]:
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
    except Exception as e:
        console.print(f"[red]could not generate preview: {e}[/red]")

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

        header_to_idx = {header: i for i, header in enumerate(csv_headers)}

        with file_path.open("r", encoding="utf-8-sig") as f:
            f.readline()  # skip header

            values_to_save = []
            for line in f:
                if not line.strip():
                    continue
                parts = line.strip().split(separator)
                row_data = {}
                for csv_header, column_name in column_map.items():
                    if column_name in columns_to_import:
                        idx = header_to_idx.get(csv_header)
                        if idx is not None and idx < len(parts):
                            row_data[column_name] = parts[idx]
                if row_data:
                    values_to_save.append(row_data)

            if values_to_save:
                storage_instance.save(table_name, values_to_save)
        console.print("[green]extraction complete[/green]")
    except Exception as e:
        console.print(f"[red]an error occurred during extraction: {e}[/red]")
        raise typer.Abort()
