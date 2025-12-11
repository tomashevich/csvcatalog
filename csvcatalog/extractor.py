import os
from tabulate import tabulate
from .registry import registry
from .saver import Saver


class Extractor:
    def __init__(self, saver: Saver) -> None:
        self.file: str | None = None
        self.headers: list[str] = []
        self.separator: str = ","
        self.table: str = "temp"
        self.saver = saver

        self._register_commands()

    def _register_commands(self) -> None:
        registry.register(
            "ex.help",
            self._help,
            description="Help about extractor module.",
            aliases=["ex"],
        )
        registry.register(
            "ex.file",
            self._set_file_command,
            description="Set a CSV file.",
            example="ex.file data.csv",
        )
        registry.register(
            "ex.sep",
            self._set_separator_command,
            description="Set a CSV separator.",
            example="ex.sep ';'",
        )
        registry.register(
            "ex.headers",
            self._set_headers_command,
            description="Set file headers.",
            example="ex.headers id name age",
        )
        registry.register(
            "ex.preview",
            self._preview_command,
            description="Preview the data.",
            example="ex.preview 10",
        )
        registry.register(
            "ex.table",
            self._set_table_command,
            description="Set table name.",
            example="ex.table users",
        )
        registry.register(
            "ex.run",
            self._run_command,
            description="Extract data into table.",
            aliases=["ex.extract"],
        )

    def clear_file_info(self) -> None:
        self.file = None
        self.headers = []
        self.table = "temp"

    def set_headers(self, *headers: str) -> None:
        if self.file is None:
            raise Exception("No file set")

        with open(self.file, "r", encoding="utf-8-sig") as f:
            line = f.readline()
            if not line:
                raise Exception("Empty file")

            required_len = len(line.split(self.separator))
            if len(headers) != required_len:
                raise Exception(
                    f"Wrong number of headers: {len(headers)}/{required_len}"
                )
        self.headers = list(headers)

    def set_headers_from_file(self) -> None:
        if self.file is None:
            raise Exception("No file set")

        with open(self.file, "r", encoding="utf-8-sig") as f:
            line = f.readline()
            if not line:
                raise Exception("Empty file")
            self.headers = line.strip().split(self.separator)

    def set_file(self, file_path: str) -> None:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: '{file_path}'")
        if os.path.isdir(file_path):
            raise IsADirectoryError(f"Not a file: '{file_path}'")
        if not file_path.endswith(".csv"):
            print(f"warning: {file_path} is not a .csv file")
        self.file = file_path

    def preview(self, count: int = 5) -> None:
        if self.file is None:
            raise Exception("no file set")

        with open(self.file, "r", encoding="utf-8-sig") as f:
            lines = [
                line.strip().split(self.separator)
                for i, line in enumerate(f)
                if i < count
            ]
        print(tabulate(lines, headers=self.headers, tablefmt="grid"))

    def _help(self) -> None:
        print(
            "Extractor: A tool to extract data from CSV files.\n"
            "Works with the Saver module ('s.help').\n\n"
            "Current configuration:\n"
            f"  - File: {self.file}\n"
            f"  - Headers: {self.headers}\n"
            f"  - Separator: '{self.separator}'\n"
            f"  - Target Table: {self.table}\n\n"
            "Usage:\n"
            "  1. 'ex.file <path-to-file.csv>' - Set the source file.\n"
            "  2. 'ex.sep <separator>' - (Optional) Set the field separator.\n"
            "  3. 'ex.run' - Start extracting and saving the data.\n"
        )
        print("Available extractor commands:")
        for command in registry.all_commands():
            if command.name.startswith("ex"):
                print(f"  {command}")

    def _set_separator_command(self, sep: str) -> None:
        self.separator = sep
        self.set_headers_from_file()
        print(f"Set separator to '{self.separator}'")

    def _set_file_command(self, file_path: str) -> None:
        self.clear_file_info()
        self.set_file(file_path)
        self.set_headers_from_file()
        self.table = os.path.splitext(os.path.basename(file_path))[0].strip()
        print(f"Set file to {file_path}")

    def _set_headers_command(self, *headers: str) -> None:
        self.set_headers(*headers)
        print(f"Set headers to: {' '.join(self.headers)}")

    def _preview_command(self, count_str: str = "5") -> None:
        self.preview(int(count_str))

    def _set_table_command(self, name: str) -> None:
        self.table = name.strip()
        print(f"Set table name to '{self.table}'")

    def _run_command(self) -> None:
        if self.file is None:
            raise Exception("no file set")

        self.saver.create_table(self.table, self.headers)
        print("Preview before running:")
        self.preview(2)
        print(f"This will extract data into the '{self.table}' table.")

        if input("Continue? (y/n): ").lower().strip() != "y":
            print("Aborted.")
            return

        with open(self.file, "r", encoding="utf-8-sig") as f:
            f.readline()  # Skip header row
            values = []
            for line in f:
                if not line.strip():
                    continue
                parts = line.strip().split(self.separator)
                if len(parts) == len(self.headers):
                    values.append(dict(zip(self.headers, parts)))

            if values:
                self.saver.save(self.table, values)
        print("Extraction complete!")
