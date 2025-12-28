from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from typer import Context

from .. import config

app = typer.Typer(
    invoke_without_command=True, help="manage saved reusable regex filters"
)
console = Console()


def list_filters():
    """lists all saved filters"""
    settings = config.load_config()
    if not settings.filters:
        console.print("[yellow]no saved filters found[/yellow]")
        return

    table = Table("name", "regex pattern")
    for name, pattern in settings.filters.items():
        table.add_row(name, pattern)
    console.print(table)


@app.callback(invoke_without_command=True)
def main(ctx: Context):
    """manage saved reusable regex filters"""
    if ctx.invoked_subcommand is None:
        list_filters()


@app.command()
def add(
    name: Annotated[str, typer.Argument(help="the name of the filter")],
    pattern: Annotated[str, typer.Argument(help="the regex pattern for the filter")],
):
    """adds or updates a saved filter"""
    settings = config.load_config()
    settings.filters[name] = pattern
    config.save_config(settings)
    console.print(f"[green]filter '{name}' saved successfully[/green]")


@app.command()
def remove(
    name: Annotated[
        str | None, typer.Argument(help="the name of the filter to remove")
    ] = None,
):
    """removes one or more saved filters"""
    settings = config.load_config()
    if not settings.filters:
        console.print("[yellow]no saved filters to remove[/yellow]")
        return

    if name:
        if name in settings.filters:
            del settings.filters[name]
            config.save_config(settings)
            console.print(f"[green]filter '{name}' removed[/green]")
        else:
            console.print(f"[red]filter '{name}' not found[/red]")
            raise typer.Abort()
    else:
        # interactive removal
        import questionary

        choices = list(settings.filters.keys())
        filters_to_remove = questionary.checkbox(
            "select filters to remove", choices=choices
        ).ask()

        if not filters_to_remove:
            console.print("no filters selected aborting")
            return

        for f_name in filters_to_remove:
            del settings.filters[f_name]

        config.save_config(settings)
        console.print(
            f"[green]successfully removed {len(filters_to_remove)} filter(s)[/green]"
        )
