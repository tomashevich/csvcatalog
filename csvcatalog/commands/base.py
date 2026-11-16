from abc import ABC, abstractmethod
from typing import Generic, ParamSpec, cast

import typer
from rich.console import Console
from typer import Context

from ..config import Settings
from ..storage import BaseStorage

console = Console()

P = ParamSpec("P")


def get_command_context(ctx: Context) -> tuple[BaseStorage, Settings]:
    """extract the typed storage and settings objects from a typer context"""
    obj = cast(dict[str, object], cast(object, ctx.obj))
    return (
        cast(BaseStorage, obj["storage"]),
        cast(Settings, obj["settings"]),
    )


class CommandBase(ABC, Generic[P]):
    """
    an abstract base class for commands
    """

    def __init__(self, storage: BaseStorage, settings: Settings):
        self.storage: BaseStorage = storage
        self.settings: Settings = settings

    def run(self, *args: P.args, **kwargs: P.kwargs) -> None:
        """
        method called by typer. wraps the command logic in a generic error handler
        """
        try:
            self.execute(*args, **kwargs)
        except typer.Abort:
            # re-raise abort exceptions to let typer handle them
            raise
        except Exception as e:
            console.print(f"[bold red]an unexpected error occurred: {e}[/bold red]")
            raise typer.Abort() from e

    @abstractmethod
    def execute(self, *args: P.args, **kwargs: P.kwargs) -> None:
        """
        the main entry method for the cmd logic
        """
        ...
