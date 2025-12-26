import questionary
import typer


def define_filters_loop(columns_to_export: list[str]) -> dict[str, str]:
    """runs the interactive loop to define regex filters for a set of columns"""
    filters: dict[str, str] = {}
    while True:
        choices = [col for col in columns_to_export if col not in filters] + ["Done"]
        column_to_filter = questionary.select(
            "select a column to filter (or 'done'):", choices=choices
        ).ask()

        if column_to_filter is None:
            raise typer.Abort()
        if column_to_filter == "Done":
            break

        regex_filter = questionary.text(
            f"enter regex filter for '{column_to_filter}':"
        ).ask()
        if regex_filter is None:
            raise typer.Abort()
        filters[column_to_filter] = regex_filter
    return filters


def prompt_for_filters(columns_to_export: list[str]) -> dict[str, str]:
    """prompts user if they want to add filters, and if so, runs the filter definition loop"""
    if not questionary.confirm("add filters?", default=False).ask():
        return {}
    return define_filters_loop(columns_to_export)
