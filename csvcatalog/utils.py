from datetime import UTC, datetime
from pathlib import Path

import questionary
import typer
from questionary import Separator
from rich.console import Console

from . import config, prompts
from .config import Settings

console = Console()


def file_creation_time(path: Path) -> datetime:
    """return the file creation time in UTC, falling back to inode change time"""
    stat = path.stat()
    timestamp = getattr(stat, "st_birthtime", stat.st_ctime)
    return datetime.fromtimestamp(timestamp, UTC)


def define_filters_loop(
    columns_to_export: list[str], settings: Settings
) -> dict[str, list[str]]:
    """runs the interactive loop to define regex filters for a set of columns"""
    filters: dict[str, list[str]] = {}
    while True:
        # create choices that show which columns already have filters
        col_choices: list[str] = []
        for col in columns_to_export:
            filter_count = len(filters.get(col, []))
            label = f"{col} ({filter_count} filter(s))" if filter_count > 0 else col
            col_choices.append(label)
        col_choices.append("[continue]")

        # parse the selection to get the clean column name
        raw_selection = prompts.ask_text(
            questionary.select(
                "select a column to apply a filter to (or 'done'):",
                choices=col_choices,
            )
        )

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

        selected_filter = prompts.ask_text(
            questionary.select(
                f"select a filter for column '{column_to_filter}':",
                choices=filter_choices,
            )
        )

        if selected_filter is None:
            raise typer.Abort()

        regex_pattern = ""
        if selected_filter == "New one-time regex":
            raw_pattern = prompts.ask_text(questionary.text("enter regex pattern:"))
            if raw_pattern is None:
                raise typer.Abort()
            regex_pattern = raw_pattern

            # ask to save the new regex
            if prompts.ask_bool(
                questionary.confirm(
                    "do you want to save this new regex for future use?", default=False
                )
            ):
                filter_name = prompts.ask_text(
                    questionary.text("enter a name for this filter:")
                )
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
    if not prompts.ask_bool(
        questionary.confirm("add filters to include/exclude rows?", default=False)
    ):
        return {}
    return define_filters_loop(columns_to_export, settings)
