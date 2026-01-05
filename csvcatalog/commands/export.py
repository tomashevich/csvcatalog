import csv
from typing import Annotated, Any

import questionary
import typer
from questionary import Choice
from rich.console import Console
from rich.markup import escape

from .. import utils
from .base import CommandBase

console = Console()


class ExportCommand(CommandBase):
    def _configure_table_for_export(self, table_name: str) -> dict[str, Any]:
        """runs the full interactive configuration for exporting a single table"""
        table = self.storage.get_table(table_name)
        if not table:
            console.print(f"[red]table '{table_name}' not found[/red]")
            raise typer.Abort()

        # 1. select columns
        col_choices = [Choice(col, checked=True) for col in table.columns]
        columns_to_export = questionary.checkbox(
            f"select columns to export from '{table_name}'",
            choices=col_choices,
        ).ask()
        if not columns_to_export:
            console.print("[red]no columns selected, aborting[/red]")
            raise typer.Abort()

        # 2. define filters
        filters = utils.prompt_for_filters(columns_to_export, self.settings)

        # 3. ask for unique rows
        export_distinct = questionary.confirm(
            "export only unique rows?", default=False
        ).ask()

        # 4. get limit
        limit_str = questionary.text(
            f"how many rows to export? (all/{table.count})", default="all"
        ).ask()

        if limit_str is None:
            raise typer.Abort()

        limit = -1
        if limit_str.lower() != "all":
            try:
                limit = int(limit_str)
                if limit < 0:
                    raise ValueError
            except ValueError:
                console.print("[red]invalid input, using 'all'[/red]")
                limit = -1

        # 5. get filename
        default_filename = f"{table_name}.csv"
        output_filename = questionary.text(
            "enter filename for export:", default=default_filename
        ).ask()
        if not output_filename:
            output_filename = default_filename
        if not output_filename.lower().endswith(".csv"):
            output_filename += ".csv"

        return {
            "table_name": table_name,
            "columns": columns_to_export,
            "filters": filters,
            "distinct": export_distinct,
            "limit": limit,
            "output_filename": output_filename,
        }

    def _execute_export(self, export_config: dict[str, Any]):
        """executes the export query and writes the results to a csv file"""
        table_name = export_config["table_name"]
        columns_to_export = export_config["columns"]
        filters = export_config["filters"]
        export_distinct = export_config["distinct"]
        limit = export_config["limit"]
        output_filename = export_config["output_filename"]

        # build query
        select_keyword = "SELECT DISTINCT" if export_distinct else "SELECT"
        columns_str = ", ".join(f'"{c}"' for c in columns_to_export)
        query = f'{select_keyword} {columns_str} FROM "{table_name}"'
        params = []

        if filters:
            console.print(f"\n[bold]filters for '{table_name}':[/bold]")
            where_clauses = []
            for col, patterns in filters.items():
                for regex in patterns:
                    console.print(
                        f"  - [cyan]{col}[/cyan] -> [magenta]'{escape(regex)}'[/magenta]"
                    )
                    where_clauses.append(f'"{col}" REGEXP ?')
                    params.append(regex)
            query += " WHERE " + " AND ".join(where_clauses)

        if limit != -1:
            query += f" LIMIT {limit}"

        try:
            results = self.storage.sql(query, params)
            if not results:
                console.print(
                    f"[yellow]no data found for '{table_name}' with the given filters[/yellow]"
                )
                return

            with open(output_filename, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(columns_to_export)
                for row in results:
                    writer.writerow(row.values())

            console.print(
                f"[green]successfully exported {len(results)} rows to '{output_filename}'[/green]"
            )
        except Exception as e:
            console.print(f"[red]error during export of '{output_filename}': {e}[/red]")
            # no abort here to allow other tables in bulk export to continue

    def execute(
        self,
        table_names: Annotated[
            list[str] | None,
            typer.Argument(help="the name of the table(s) to export"),
        ] = None,
    ):
        """export one or more tables to csv files"""
        tables_to_export = table_names

        if not tables_to_export:
            all_tables = self.storage.get_tables()
            if not all_tables:
                console.print("[yellow]no tables found in database[/yellow]")
                raise typer.Abort()

            choices = [Choice(table.name, checked=True) for table in all_tables]
            selected_tables = questionary.checkbox(
                "select tables to export (space to select/deselect, enter to confirm)",
                choices=choices,
            ).ask()

            if selected_tables is None:  # user cancelled with ctrl+c
                console.print("[red]aborted[/red]")
                raise typer.Abort()

            tables_to_export = selected_tables

        if not tables_to_export:
            console.print("[red]no tables selected, aborting[/red]")
            raise typer.Abort()

        if len(tables_to_export) == 1:
            config = self._configure_table_for_export(tables_to_export[0])
            self._execute_export(config)
        else:
            # for multiple tables, start with default configs
            export_configs = {}
            for name in tables_to_export:
                table = self.storage.get_table(name)
                if not table:
                    console.print(
                        f"[yellow]table '{name}' not found, skipping[/yellow]"
                    )
                    continue
                export_configs[name] = {
                    "table_name": name,
                    "columns": table.columns,
                    "filters": {},
                    "distinct": False,
                    "limit": -1,
                    "output_filename": f"{name}.csv",
                }

            # loop to allow user to fully configure specific tables
            while True:
                choices = list(export_configs.keys()) + ["[continue]"]
                table_to_configure = questionary.select(
                    "select a table to configure, or continue to export:",
                    choices=choices,
                ).ask()

                if table_to_configure is None:
                    raise typer.Abort()
                if table_to_configure == "[continue]":
                    break

                console.print(
                    f"\nrunning interactive setup for '{table_to_configure}'..."
                )
                # run the full interactive configuration for the selected table
                new_config = self._configure_table_for_export(table_to_configure)
                # update the configuration for that table
                export_configs[table_to_configure] = new_config
                console.print(
                    f"[green]export settings for '{table_to_configure}' updated[/green]\n"
                )

            console.print(f"\nstarting bulk export for {len(export_configs)} tables...")
            for config in export_configs.values():
                self._execute_export(config)
            console.print("\n[bold green]bulk export complete[/bold green]")
