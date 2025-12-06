class Command:
    def __init__(
        self,
        name: str,
        func,
        description: str = "",
        example: str = "",
    ):
        self.name = name
        self.description = description
        self.example = example

        self.func = func

    def execute(self, args: list[any] | None = None) -> None:
        if args is None:
            self.func()
            return

        self.func(args)

    def __str__(self) -> str:
        return f"{self.name}{f': {self.description}' if self.description else ''} {'{' + self.example + '}' if self.example else ''}"
