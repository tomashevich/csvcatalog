import csv
import re
from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from .. import utils
from ..storage import BaseStorage

console = Console()

# constants for batch processing
BATCH_SIZE = 10_000


def _row_is_filtered_out(row_data: dict[str, str], filters: dict[str, str]) -> bool:
    """returns true if the row should be skipped based on the defined filters"""
    if not filters:
        return False
    for col, pattern in filters.items():
        value_to_check = row_data.get(col, "")
        if not re.search(pattern, value_to_check):
            return True  # skip row if any filter does not match
    return False


def _get_csv_data(
    file_path: Path, separator: str, encoding: str
) -> tuple[list[str], list[list[str]]]:
    """helper to read csv headers and preview rows with specified encoding"""
    try:
        with file_path.open("r", encoding=encoding, newline="") as f:
            reader = csv.reader(f, delimiter=separator)
            csv_headers = next(reader)
            preview_rows = [row for i, row in enumerate(reader) if i < 5]
        return csv_headers, preview_rows
    except StopIteration:
        raise typer.BadParameter(
            "file appears to be empty or has only a header"
        ) from None
    except UnicodeDecodeError as e:
        raise typer.BadParameter(
            f"could not decode file with '{encoding}' encoding: {e}"
        ) from e
    except Exception as e:
        raise typer.BadParameter(f"could not read file: {e}") from e


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
    encoding: Annotated[str, typer.Option(help="encoding of the csv file")] = "utf-8",
):
    """run interactive wizard to extract data from a csv file"""
    console.print(f"starting extraction for '{file_path}'")
    storage_instance: BaseStorage = ctx.obj

    # set separator
    separator = questionary.text("enter csv separator:", default=",").ask()
    if not separator:
        console.print("[red]aborted[/red]")
        raise typer.Abort()

    current_encoding = encoding
    csv_headers: list[str] = []
    preview_rows: list[list[str]] = []

    # encoding selection and preview
    while True:
        try:
            csv_headers, preview_rows = _get_csv_data(
                file_path, separator, current_encoding
            )

            console.print(
                f"\n[bold]raw preview with encoding '{current_encoding}':[/bold]"
            )
            console.print(separator.join(csv_headers))
            for row in preview_rows:
                console.print(separator.join(row))

            confirm_encoding = questionary.confirm(
                f"is '{current_encoding}' the correct encoding for the preview?"
            ).ask()
            if confirm_encoding is None:
                console.print("[red]aborted[/red]")
                raise typer.Abort()

            if not confirm_encoding:
                new_encoding = questionary.text(
                    "enter new encoding (e.g., utf-8, utf-8-sig, latin-1):",
                    default=current_encoding,
                ).ask()
                if not new_encoding:
                    console.print("[red]aborted[/red]")
                    raise typer.Abort()
                current_encoding = new_encoding
                continue
            break
        except typer.BadParameter as e:
            console.print(f"[red]error: {e}[/red]")
            new_encoding = questionary.text(
                "enter new encoding (e.g., utf-8, utf-8-sig, latin-1):",
                default=current_encoding,
            ).ask()
            if not new_encoding:
                console.print("[red]aborted[/red]")
                raise typer.Abort() from None
            current_encoding = new_encoding

    final_encoding = current_encoding

    console.print("\n[bold]define database column names for each csv header[/bold]")
    console.print("press enter to accept the default name")

    column_map = {}
    for header in csv_headers:
        column_name = questionary.text(
            f"  csv header '{header}' -> column name:", default=header
        ).ask()
        if not column_name:
            console.print("[red]aborted[/red]")
            raise typer.Abort()
        column_map[header] = column_name

    # select columns
    columns_to_import = questionary.checkbox(
        "select the columns you want to import",
        choices=list(column_map.values()),
    ).ask()
    if not columns_to_import:
        console.print("[red]no columns selected, aborting[/red]")
        raise typer.Abort()

    # define filters
    filters = utils.prompt_for_filters(columns_to_import)

    # table name
    default_table_name = file_path.stem.strip()
    table_name = questionary.text("enter table name:", default=default_table_name).ask()
    if not table_name:
        console.print("[red]aborted[/red]")
        raise typer.Abort()

    # table description
    description = questionary.text("enter table description:", default="no").ask()
    if description is None:  # if user presses ctrl+c
        console.print("[red]aborted[/red]")
        raise typer.Abort()

    # preview data
    console.print("\n[bold]preview of data to be imported:[/bold]")
    header_to_idx = {header: i for i, header in enumerate(csv_headers)}
    data_to_preview = []
    for line in preview_rows:
        row_data = {}
        for csv_header, column_name in column_map.items():
            if column_name not in columns_to_import:
                continue
            idx = header_to_idx.get(csv_header)
            if idx is None or idx >= len(line):
                continue
            row_data[column_name] = line[idx]

        if not row_data or _row_is_filtered_out(row_data, filters):
            continue
        data_to_preview.append(row_data)

    if data_to_preview:
        table = Table(show_header=True, header_style="bold magenta")
        for col in columns_to_import:
            table.add_column(col)
        for row in data_to_preview:
            table.add_row(*(row.get(col, "") for col in columns_to_import))
        console.print(table)
    else:
        console.print(
            "[yellow]no data to preview (all 5 preview rows were filtered out)[/yellow]"
        )

    # summary
    console.print("\n[bold]summary[/bold]")
    console.print(f"  file:       {file_path}")
    console.print(f"  table:      {table_name}")
    console.print(
        f"  description:{description if description != 'no' else '[grey50]noription[/grey50]'} "
    )
    console.print(f"  separator:  '{separator}'")
    console.print(f"  columns:    {', '.join(columns_to_import)}")
    console.print("[bold]column mapping:[/bold]")
    for csv_h, db_f in column_map.items():
        if db_f not in columns_to_import:
            continue
        console.print(f"  - '{csv_h}' -> '{db_f}'")
    if filters:
        console.print(
            "[bold]filters to apply (only matching rows will be imported):[/bold]"
        )
        for col, regex in filters.items():
            console.print(
                f"  - [cyan]{col}[/cyan] must match regex -> [magenta]'{escape(regex)}'[/magenta]"
            )

    proceed = questionary.confirm("proceed with extraction?").ask()
    if not proceed:
        console.print("[red]aborted[/red]")
        raise typer.Abort()

    # extraction
    try:
        console.print("starting extraction...")
        storage_instance.create_table(table_name, columns_to_import)
        if description != "no":
            storage_instance.update_description(table_name, description)

        with file_path.open("r", encoding=final_encoding, newline="") as f:
            reader = csv.reader(f, delimiter=separator)
            next(reader)  # skip header

            batch = []
            total_saved = 0
            filtered_out_count = 0
            for _, row_parts in enumerate(reader):
                if not row_parts:
                    continue

                row_data = {}
                for csv_header, column_name in column_map.items():
                    if column_name not in columns_to_import:
                        continue

                    idx = header_to_idx.get(csv_header)
                    if idx is None or idx >= len(row_parts):
                        continue

                    row_data[column_name] = row_parts[idx]

                if not row_data:
                    continue

                if _row_is_filtered_out(row_data, filters):
                    filtered_out_count += 1
                    continue

                batch.append(row_data)

                if len(batch) < BATCH_SIZE:
                    continue

                storage_instance.save(table_name, batch)
                total_saved += len(batch)
                console.print(f"  ... saved {total_saved} rows")
                batch.clear()

            if batch:
                storage_instance.save(table_name, batch)
                total_saved += len(batch)

        console.print(
            f"[green]extraction complete. saved {total_saved} rows.[/green] ({filtered_out_count} rows filtered out)"
        )

    except Exception as e:
        console.print(f"[red]an error occurred during extraction: {e}[/red]")
        raise typer.Abort() from e
