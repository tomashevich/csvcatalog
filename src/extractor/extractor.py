import os

from tabulate import tabulate

from src.cmd.command import Command


class Extractor:
    def __init__(self) -> None:
        self.file: str | None = None
        self.headers: list[str] = []
        self.seperator: str = ","

        self.commands = [
            Command(
                "extractor",
                self.command_help_handler,
                description="help about extractor module",
                aliases=["ex", "ex.help", "extractor.help"],
            ),
            Command(
                "extractor.file",
                self.command_file_handler,
                description="set a csv file",
                example="extractor.file data.csv",
                aliases=["ex.file"],
            ),
            Command(
                "extractor.sep",
                self.command_sep_handler,
                description="set a csv separator",
                example="extractor.sep",
                aliases=["ex.sep"],
            ),
            Command(
                "extractor.headers",
                self.command_headers_handler,
                description="set file headers",
                example="extractor.headers id name age",
                aliases=["ex.headers"],
            ),
            Command(
                "extractor.preview",
                self.command_preview_handler,
                description="preview the data",
                example="extractor.preview",
                aliases=["ex.preview"],
            ),
        ]

    def clear_file_info(self) -> None:
        self.file = None
        self.headers = []

    def set_headers(self, *args) -> None:
        if self.file is None:
            raise Exception("No file set")

        self.headers = list(*args)

    def set_headers_from_file(self) -> None:
        if self.file is None:
            raise Exception("No file set")

        with open(self.file, "r", encoding="utf-8") as f:
            line = f.readline()
            if not line:
                raise Exception("Empty file")

            self.headers = line.strip().split(self.seperator)

    def set_file(self, file_path: str) -> None:
        if not file_path.endswith("csv"):
            raise Exception(f"Invalid file format: {file_path}")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if os.path.isdir(file_path):
            raise Exception(f"Directory not allowed: {file_path}")

        self.clear_file_info()

        self.file = file_path

    def preview(self, count: int = 5) -> str:
        if self.file is None:
            raise Exception("no file set")

        with open(self.file, "r", encoding="utf-8") as f:
            lines = []
            for i in range(count):
                line = f.readline()
                if not line:
                    break  # end of file

                lines.append(line.split(self.seperator))

            print(tabulate(lines, headers=self.headers, tablefmt="grid"))

    def run(self) -> None:
        if self.file is None:
            raise Exception("no file set")

        with open(self.file, "r", encoding="utf-8") as f:
            for line in f:
                if not line:
                    break  # end of file

                # TODO: make save

    # ---
    # Commands
    # ---

    def command_help_handler(self) -> None:
        print(
            f"""Extractor help:
  Extractor using as a command-line tool to extract data from csv files.
  Working with Saver module ('saver.help').

Current vars:
  ex.file: {self.file}
  ex.headers: {self.headers}
  ex.sep: {self.seperator}

How to use:
  1st: 'ex.file <path-to-file.csv>' set file
  2nd: 'ex.sep <separator>' set separator (',' by default)
  3rd: 'ex.run' start extracting data and saving it line by line
            """
        )
        print("Available extractor commands:")
        for command in self.commands:
            print(f"  {command}")

    def command_sep_handler(self, *args) -> None:
        self.seperator = args[0]
        print(f"setted separator to '{self.seperator}'")

    def command_file_handler(self, *args) -> None:
        self.set_file(args[0])
        self.set_headers_from_file()
        print(f"setted file {args[0]}")

    def command_headers_handler(self, *args) -> None:
        self.set_headers(args)
        print(f"setted headers to {' '.join(self.headers)}")

    def command_preview_handler(self, *args) -> None:
        count = 5
        if len(args) > 0:
            if args[0].isdigit():
                count = int(args[0])

        self.preview(count)

    def command_run_handler(self) -> None:
        print("starting extraction...")
        self.run()
