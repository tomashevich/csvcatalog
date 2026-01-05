import questionary
import typer
from questionary import Separator
from rich.console import Console

from . import config
from .config import Settings

console = Console()


def define_filters_loop(
    columns_to_export: list[str], settings: Settings
) -> dict[str, list[str]]:
    """runs the interactive loop to define regex filters for a set of columns"""
    filters: dict[str, list[str]] = {}
    while True:
        # create choices that show which columns already have filters
        col_choices = []
        for col in columns_to_export:
            filter_count = len(filters.get(col, []))
            label = f"{col} ({filter_count} filter(s))" if filter_count > 0 else col
            col_choices.append(label)
        col_choices.append("[continue]")

        # parse the selection to get the clean column name
        raw_selection = questionary.select(
            "select a column to apply a filter to (or 'done'):", choices=col_choices
        ).ask()

        if raw_selection is None:
            raise typer.Abort()
        if raw_selection == "[continue]":
            break

        column_to_filter = raw_selection.split(" (")[0]

        # select a filter (new or saved)
        filter_choices: list[str | Separator] = ["New one-time regex"]
        if settings.filters:
            filter_choices.append(Separator())
            filter_choices.extend(settings.filters.keys())

        selected_filter = questionary.select(
            f"select a filter for column '{column_to_filter}':", choices=filter_choices
        ).ask()

        if selected_filter is None:
            raise typer.Abort()

        regex_pattern = ""
        if selected_filter == "New one-time regex":
            regex_pattern = questionary.text("enter regex pattern:").ask()
            if regex_pattern is None:
                raise typer.Abort()

            # ask to save the new regex
            if questionary.confirm(
                "do you want to save this new regex for future use?", default=False
            ).ask():
                filter_name = questionary.text("enter a name for this filter:").ask()
                if filter_name:
                    settings.filters[filter_name] = regex_pattern
                    config.save_config(settings)
                    console.print(f"[green]filter '{filter_name}' saved[/green]")
        else:
            # used a saved filter
            regex_pattern = settings.filters[selected_filter]

        if regex_pattern:
            if column_to_filter not in filters:
                filters[column_to_filter] = []
            filters[column_to_filter].append(regex_pattern)

    return filters


def prompt_for_filters(
    columns_to_export: list[str], settings: Settings
) -> dict[str, list[str]]:
    """prompts user if they want to add filters, and if so, runs the filter definition loop"""
    if not questionary.confirm(
        "add filters to include/exclude rows?", default=False
    ).ask():
        return {}
    return define_filters_loop(columns_to_export, settings)
