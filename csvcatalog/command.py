from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Command:
    name: str
    handler: Callable[..., Any]
    description: str = ""
    example: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def execute(self, *args: str) -> None:
        try:
            self.handler(*args)
        except Exception as e:
            print(f"error: failed to execute '{self.name}': {e}")

    def __str__(self) -> str:
        base = f"{self.name}"
        if self.description:
            base += f": {self.description}"
        if self.example:
            base += f" (e.g., '{self.example}')"
        return base
