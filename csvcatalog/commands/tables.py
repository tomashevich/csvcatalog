import datetime
from enum import Enum
from typing import Annotated

import questionary
import typer
from questionary import Choice
from rich.console import Console
from rich.table import Table
from typer import Context

from .. import storage
from ..storage import Table as DbTable
from .base import CommandBase

app = typer.Typer(help="interact with tables")
console = Console()


class SortOption(str, Enum):
    table_name = "name"
    rows = "rows"
    date = "date"


class TablesListCommand(CommandBase):
    def execute(
        self,
        description_filter: str | None,
        min_rows: int | None,
        created_after: str | None,
        sort_by: str | None,
    ):
        """list all tables in the database"""
        tables = self.storage.get_tables(
            description_filter=description_filter,
            min_rows=min_rows,
            created_after=created_after,
            sort_by=sort_by,
        )

        if not tables:
            console.print("[yellow]no tables found matching the criteria[/yellow]")
            return

        # display tables
        rich_table = Table(
            title="available tables",
            show_header=True,
            header_style="bold magenta",
        )
        rich_table.add_column("name", style="cyan")
        rich_table.add_column("description")
        rich_table.add_column("columns")
        rich_table.add_column("row count", justify="right")
        rich_table.add_column("created at")

        for table in tables:  # sorting is now done in db
            created_at_str = table.created_at.split("T")[0]
            rich_table.add_row(
                table.name,
                table.description or "[grey50]n/a[/grey50]",
                ", ".join(table.columns),
                str(table.count),
                created_at_str,
            )

        console.print(rich_table)


@app.command(name="list")
def list_tables(
    ctx: Context,
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            "-d",
            help="filter tables by their description (case-insensitive)",
        ),
    ] = None,
    rows: Annotated[
        int | None,
        typer.Option(
            "--rows",
            "-r",
            help="filter tables by minimum row count",
            min=0,
        ),
    ] = None,
    date: Annotated[
        str | None,
        typer.Option(
            "--date",
            help="filter by creation date (yyyy-mm-dd), showing tables created on or after this date",
        ),
    ] = None,
    sort: Annotated[
        SortOption,
        typer.Option(
            "--sort",
            "-s",
            help="sort tables by name, rows, or date",
            case_sensitive=False,
        ),
    ] = SortOption.table_name,
):
    """list all tables in the database"""
    if date:
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            console.print("[red]invalid date format. please use yyyy-mm-dd[/red]")
            raise typer.Abort() from None

    cmd = TablesListCommand(ctx.obj["storage"], ctx.obj["settings"])
    cmd.execute(
        description_filter=description,
        min_rows=rows,
        created_after=date,
        sort_by=sort.value,
    )


class TablesEditCommand(CommandBase):
    def execute(self, table_name: str | None):
        """interactive wizard to edit table metadata"""
        if not table_name:
            tables = self.storage.get_tables()
            if not tables:
                console.print("[yellow]no tables found to edit[/yellow]")
                return

            table_choices = [
                Choice(title=f"{t.name}", value=t.name)
                for t in sorted(tables, key=lambda t: t.name)
            ]
            table_name = questionary.select(
                "select the table you want to edit:", choices=table_choices
            ).ask()
            if not table_name:
                raise typer.Abort()

        table = self.storage.get_table(table_name)
        if not table:
            console.print(f"[red]error: table '{table_name}' not found[/red]")
            raise typer.Abort()

        edit_choice = questionary.select(
            "what do you want to edit?",
            choices=[
                Choice("name", value="name"),
                Choice("description", value="description"),
                Choice(
                    f"date (current: {table.created_at.split('T')[0]})", value="date"
                ),
            ],
        ).ask()

        if not edit_choice:
            raise typer.Abort()

        if edit_choice == "name":
            self._edit_name(table)
        elif edit_choice == "description":
            self._edit_description(table)
        elif edit_choice == "date":
            self._edit_date(table)

    def _edit_name(self, table: DbTable):
        new_name_raw = questionary.text(
            "enter new table name:", default=table.name
        ).ask()
        if not new_name_raw or new_name_raw == table.name:
            console.print("[yellow]name not changed[/yellow]")
            return

        new_name = storage.sanitize_identifier(new_name_raw)
        if new_name != new_name_raw:
            console.print(f"[yellow]name sanitized to '{new_name}'[/yellow]")

        if self.storage.get_table(new_name):
            console.print(f"[red]error: table '{new_name}' already exists[/red]")
            raise typer.Abort()

        self.storage.rename_table(old_name=table.name, new_name=new_name)
        console.print(
            f"[green]table '{table.name}' was successfully renamed to '{new_name}'[/green]"
        )

    def _edit_description(self, table: DbTable):
        new_description = questionary.text(
            "enter new description:", default=table.description or ""
        ).ask()
        if new_description is None or new_description == table.description:
            console.print("[yellow]description not changed[/yellow]")
            return

        self.storage.update_description(table.name, new_description)
        console.print(
            f"[green]description for table '{table.name}' was successfully updated[/green]"
        )

    def _edit_date(self, table: DbTable):
        current_date_str = table.created_at.split("T")[0]
        new_date_str = questionary.text(
            "enter new date (yyyy-mm-dd):", default=current_date_str
        ).ask()

        if not new_date_str or new_date_str == current_date_str:
            console.print("[yellow]date not changed[/yellow]")
            return

        try:
            new_date = datetime.datetime.strptime(new_date_str, "%Y-%m-%d")
            try:
                original_time = datetime.datetime.fromisoformat(table.created_at).time()
                new_datetime = new_date.replace(
                    hour=original_time.hour,
                    minute=original_time.minute,
                    second=original_time.second,
                    microsecond=original_time.microsecond,
                )
            except ValueError:
                new_datetime = new_date

            self.storage.update_created_at(table.name, new_datetime.isoformat())
            console.print(
                f"[green]date for table '{table.name}' was successfully updated[/green]"
            )
        except ValueError:
            console.print("[red]invalid date format. please use yyyy-mm-dd[/red]")
            raise typer.Abort() from None


@app.command(name="edit")
def edit_table(
    ctx: Context,
    table_name: Annotated[
        str | None,
        typer.Argument(help="the name of the table to edit"),
    ] = None,
):
    """edit table details (name, description, date)"""
    cmd = TablesEditCommand(ctx.obj["storage"], ctx.obj["settings"])
    cmd.execute(table_name=table_name)
