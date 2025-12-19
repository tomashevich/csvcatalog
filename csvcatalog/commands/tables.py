import typer
from rich.console import Console
from rich.table import Table

from ..storage import Storage

console = Console()

def tables(ctx: typer.Context):
    """list all tables in the database"""
    storage_instance: Storage = ctx.obj
    db_tables = storage_instance.get_tables()
    if not db_tables:
        console.print("[yellow]no tables found[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("name")
    table.add_column("columns")
    table.add_column("rows")

    for t in db_tables:
        table.add_row(t.name, ", ".join(t.columns), str(t.count))

    console.print(table)

