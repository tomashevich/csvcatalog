import os

from command import Command
from saver import Saver
from tabulate import tabulate


class Extractor:
    def __init__(self, saver: Saver) -> None:
        self.file: str | None = None
        self.headers: list[str] = []
        self.seperator: str = ","
        self.table: str = "temp"

        self.saver = saver

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
            Command(
                "extractor.table",
                self.command_table_handler,
                description="set table name",
                example="extractor.table users",
                aliases=["ex.table"],
            ),
            Command(
                "extractor.run",
                self.command_run_handler,
                description="extract data into table",
                example="extractor.extract",
                aliases=["ex.run", "ex.extract", "extractor.extract"],
            ),
        ]

    def clear_file_info(self) -> None:
        self.file = None
        self.headers = []
        self.table = "temp"

    def set_headers(self, *args) -> None:
        if self.file is None:
            raise Exception("No file set")

        with open(self.file, "r", encoding="utf-8") as f:
            line = f.readline()
            if not line:
                raise Exception("Empty file")

            headers_len = len(*args)
            required_headers_len = len(line.split(self.seperator))
            if headers_len != required_headers_len:
                raise Exception(
                    f"Wrong number of headers: {headers_len}/{required_headers_len}"
                )

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
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: '{file_path}'")

        if os.path.isdir(file_path):
            raise IsADirectoryError(f"Not a file: '{file_path}'")

        if not file_path.endswith(".csv"):
            print(f"warning: {file_path} file is not with csv extension")

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
  ex.table: {self.table}

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
        self.set_headers_from_file()
        print(f"setted separator to '{self.seperator}'")

    def command_file_handler(self, *args) -> None:
        self.clear_file_info()

        self.set_file(args[0])
        self.set_headers_from_file()
        self.table = str(os.path.splitext(os.path.basename(self.file))[0]).strip()

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

    def command_table_handler(self, *args) -> None:
        self.table = args[0].strip()
        print(f"setted table name to '{self.table}'")

    def command_run_handler(self) -> None:
        if self.file is None:
            raise Exception("no file set")

        self.saver.create_table(self.table, self.headers)

        print("check before run:")
        self.preview(2)
        print(f"extract data in '{self.table}' table")

        if input("continue? (y/n): ").lower().startswith("n"):
            return

        with open(self.file, "r", encoding="utf-8") as f:
            values = []
            headers_len = len(self.headers)
            for line in f:
                if not line:
                    break  # end of file

                parts = line.split(self.seperator)
                if len(parts) != headers_len:
                    continue

                value = {header: value for header, value in zip(self.headers, parts)}
                values.append(value)

            self.saver.save(
                self.table,
                values,
            )

        print("extraction completed!")
