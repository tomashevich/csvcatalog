import typer
from rich.console import Console
from rich.table import Table

from ..storage import BaseStorage

console = Console()


def tables(ctx: typer.Context):
    """list all tables in the database"""
    storage_instance: BaseStorage = ctx.obj
    db_tables = storage_instance.get_tables()
    if not db_tables:
        console.print("[yellow]no tables found[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("name")
    table.add_column("columns", max_width=50)
    table.add_column("description", max_width=50)
    table.add_column("rows")
    table.add_column("created at")

    for t in db_tables:
        description = t.description if t.description else "[grey50]n/a[/grey50]"
        table.add_row(
            t.name, ", ".join(t.columns), description, str(t.count), t.created_at
        )

    console.print(table)
