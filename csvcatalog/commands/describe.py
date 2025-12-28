from typing import Annotated

import typer
from rich.console import Console

from .base import CommandBase

console = Console()


class DescribeCommand(CommandBase):
    def execute(
        self,
        table_name: Annotated[
            str, typer.Argument(help="the name of the table to describe")
        ],
        description: Annotated[
            str, typer.Argument(help="the description to add to the table")
        ],
    ):
        """adds or updates a description for a table"""
        self.storage.update_description(table_name, description)
        console.print(f"description for table '{table_name}' updated")
