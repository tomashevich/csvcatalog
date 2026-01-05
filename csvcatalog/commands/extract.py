import csv
import re
from pathlib import Path
from typing import Annotated

import questionary
import typer
from questionary import Choice
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from .. import utils, storage
from .base import CommandBase

console = Console()


class ExtractCommand(CommandBase):
    # constants for batch processing
    BATCH_SIZE = 10_000

    def _row_is_filtered_out(
        self, row_data: dict[str, str], filters: dict[str, list[str]]
    ) -> bool:
        """returns true if the row should be skipped based on the defined filters"""
        if not filters:
            return False
        for col, patterns in filters.items():
            value_to_check = row_data.get(col, "")
            # all patterns for a given column must match (and condition)
            if not all(re.search(p, value_to_check) for p in patterns):
                return True
        return False

    def _get_csv_data(
        self, file_path: Path, separator: str, encoding: str
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

    def execute(
        self,
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
        encoding: Annotated[
            str, typer.Option(help="encoding of the csv file")
        ] = "utf-8",
    ):
        """run interactive wizard to extract data from a csv file"""
        console.print(f"starting extraction for '{file_path}'")

        # set separator
        separator = questionary.text("enter csv separator:", default=",").ask()
        if not separator:
            raise typer.Abort()

        current_encoding = encoding
        csv_headers: list[str] = []
        preview_rows: list[list[str]] = []

        # encoding selection and preview
        while True:
            try:
                csv_headers, preview_rows = self._get_csv_data(
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
                    raise typer.Abort()

                if not confirm_encoding:
                    new_encoding = questionary.text(
                        "enter new encoding (e.g., utf-8, utf-8-sig, latin-1):",
                        default=current_encoding,
                    ).ask()
                    if not new_encoding:
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
                    raise typer.Abort() from None
                current_encoding = new_encoding

        final_encoding = current_encoding

        # step 3: select which csv headers to import
        choices = [Choice(header, checked=True) for header in csv_headers]
        selected_csv_headers = questionary.checkbox(
            "select the csv columns you want to import (default all)",
            choices=choices,
        ).ask()
        if not selected_csv_headers:
            console.print("[red]no columns selected, aborting[/red]")
            raise typer.Abort()

        # step 4: define database column names for selected csv headers
        console.print(
            "\n[bold]define database column names. by default, the original csv header is used.[/bold]"
        )
        # set default mapping, sanitizing column names
        column_map = {
            header: storage.sanitize_identifier(header)
            for header in selected_csv_headers
        }

        while True:
            # create choices showing the current mapping
            mapping_choices = [
                f"{csv_header} -> {db_name}"
                for csv_header, db_name in column_map.items()
            ]
            mapping_choices.append("[continue]")

            choice_to_edit = questionary.select(
                "select a column to rename, or continue:", choices=mapping_choices
            ).ask()

            if choice_to_edit is None:
                raise typer.Abort()
            if choice_to_edit == "[continue]":
                break

            # parse the selected choice to get the original csv header
            csv_header_to_edit = choice_to_edit.split(" -> ")[0]
            current_db_name = column_map[csv_header_to_edit]

            new_db_name_raw = questionary.text(
                f"enter new database column name for '{csv_header_to_edit}':",
                default=current_db_name,
            ).ask()

            if not new_db_name_raw:
                # if user enters empty string, abort or revert? for now, let's abort.
                console.print("[red]column name cannot be empty. aborting.[/red]")
                raise typer.Abort()

            new_db_name = storage.sanitize_identifier(new_db_name_raw)
            if new_db_name != new_db_name_raw:
                console.print(
                    f"[yellow]name sanitized to '{new_db_name}'[/yellow]"
                )

            column_map[csv_header_to_edit] = new_db_name

        columns_to_import = list(column_map.values())

        # step 5: define filters
        filters = utils.prompt_for_filters(columns_to_import, self.settings)

        # step 6: table name
        default_table_name = storage.sanitize_identifier(file_path.stem.strip())
        table_name_raw = questionary.text(
            "enter table name:", default=default_table_name
        ).ask()
        if not table_name_raw:
            raise typer.Abort()

        table_name = storage.sanitize_identifier(table_name_raw)
        if table_name != table_name_raw:
            if not questionary.confirm(
                f"table name was sanitized to '{table_name}'. continue?",
                default=True,
            ).ask():
                raise typer.Abort()

        # step 7: table description
        description = questionary.text("enter table description:", default="no").ask()
        if description is None:  # if user presses ctrl+c
            raise typer.Abort()

        # preview data
        console.print("\n[bold]preview of data to be imported:[/bold]")
        header_to_idx = {header: i for i, header in enumerate(csv_headers)}
        data_to_preview = []
        for line in preview_rows:
            row_data = {}
            for csv_header, column_name in column_map.items():
                idx = header_to_idx.get(csv_header)
                if idx is None or idx >= len(line):
                    continue
                row_data[column_name] = line[idx]

            if not row_data or self._row_is_filtered_out(row_data, filters):
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
            console.print(f"  - '{csv_h}' -> '{db_f}'")
        if filters:
            console.print(
                "[bold]filters to apply (only matching rows will be imported):[/bold]"
            )
            for col, patterns in filters.items():
                for regex in patterns:
                    console.print(
                        f"  - [cyan]{col}[/cyan] must match regex -> [magenta]'{escape(regex)}'[/magenta]"
                    )

        proceed = questionary.confirm("proceed with extraction?").ask()
        if not proceed:
            raise typer.Abort()

        # extraction
        console.print("starting extraction...")
        self.storage.create_table(table_name, columns_to_import)
        if description != "no":
            self.storage.update_description(table_name, description)

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
                    idx = header_to_idx.get(csv_header)
                    if idx is None or idx >= len(row_parts):
                        continue
                    row_data[column_name] = row_parts[idx]

                if not row_data:
                    continue

                if self._row_is_filtered_out(row_data, filters):
                    filtered_out_count += 1
                    continue

                batch.append(row_data)

                if len(batch) < self.BATCH_SIZE:
                    continue

                self.storage.save(table_name, batch)
                total_saved += len(batch)
                console.print(f"  ... saved {total_saved} rows")
                batch.clear()

            if batch:
                self.storage.save(table_name, batch)
                total_saved += len(batch)

        console.print(
            f"[green]extraction complete. saved {total_saved} rows.[/green] ({filtered_out_count} rows filtered out)"
        )
