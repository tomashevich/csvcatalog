from typing import Callable, Any

from .command import Command


class CommandRegistry:
    """a registry for managing and retrieving commands"""

    def __init__(self):
        self._commands: dict[str, Command] = {}

    def register(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str = "",
        example: str = "",
        aliases: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        """registers a new command with the registry"""
        if aliases is None:
            aliases = tuple()

        command = Command(
            name=name,
            handler=handler,
            description=description,
            example=example,
            aliases=tuple(aliases),
        )
        self._commands[name] = command
        for alias in aliases:
            self._commands[alias] = command

    def get(self, name: str) -> Command | None:
        """retrieves a command by its name or alias"""
        return self._commands.get(name)

    def all_commands(self) -> list[Command]:
        """returns a sorted list of all unique registered commands"""
        return sorted(
            {cmd for cmd in self._commands.values()},
            key=lambda cmd: cmd.name,
        )


registry = CommandRegistry()
