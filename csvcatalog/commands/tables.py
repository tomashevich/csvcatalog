from rich.console import Console
from rich.table import Table

from .base import CommandBase

console = Console()


class TablesCommand(CommandBase):
    def execute(self):
        """list all tables in the database"""
        tables_data = self.storage.get_tables()
        if not tables_data:
            console.print("[yellow]no tables found[/yellow]")
            return

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("name")
        table.add_column("columns", max_width=50)
        table.add_column("description", max_width=50)
        table.add_column("rows")
        table.add_column("created at")

        for t in tables_data:
            description = t.description if t.description else "[grey50]n/a[/grey50]"
            table.add_row(
                t.name,
                ", ".join(t.columns),
                description,
                str(t.count),
                t.created_at,
            )

        console.print(table)
