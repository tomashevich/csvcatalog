from typing import Callable, Any

from .command import Command


class CommandRegistry:
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
        return self._commands.get(name)

    def all_commands(self) -> list[Command]:
        return sorted(
            list(set(self._commands.values())),
            key=lambda cmd: cmd.name,
        )


registry = CommandRegistry()
