from abc import ABC, abstractmethod

import typer
from rich.console import Console

from ..config import Settings
from ..storage import BaseStorage

console = Console()


class CommandBase(ABC):
    """
    an abstract base class for commands
    """

    def __init__(self, storage: BaseStorage, settings: Settings):
        self.storage = storage
        self.settings = settings

    def run(self, *args, **kwargs):
        """
        method called by typer. wraps the command logic in a generic error handler
        """
        try:
            return self.execute(*args, **kwargs)
        except typer.Abort:
            # re-raise abort exceptions to let typer handle them
            raise
        except Exception as e:
            console.print(f"[bold red]an unexpected error occurred: {e}[/bold red]")
            raise typer.Abort() from e

    @abstractmethod
    def execute(self, *args, **kwargs):
        """
        the main entry method for the cmd logic
        """
        ...
