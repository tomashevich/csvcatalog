import csv
import os
import sqlite3
from dataclasses import dataclass

from .registry import registry
from .selector import select_options


@dataclass
class Table:
    name: str
    columns: list[str]
    count: int


class Storage:
    def __init__(self, database_path: str):
        self.con: sqlite3.Connection | None = None
        self.cur: sqlite3.Cursor | None = None
        self.database_file: str = ""
        self.set_database(database_path)
        self._register_commands()

    def _register_commands(self) -> None:
        registry.register(
            "storage.help",
            self._help,
            description="Display storage help.",
            aliases=["s.help"],
        )
        registry.register(
            "storage.reload",
            self._reload,
            description="Reload database connection.",
            aliases=["s.reload"],
        )
        registry.register(
            "storage.tables",
            self._list_tables,
            description="List all tables in the database.",
            aliases=["s.tables"],
        )
        registry.register(
            "storage.db",
            self._set_database,
            description="Set database file.",
            example="storage.db /path/to/database.db",
            aliases=["s.db"],
        )
        registry.register(
            "storage.del.table",
            self._delete_table,
            description="Delete a table.",
            example="storage.del.table my_table",
            aliases=["s.del.table"],
        )
        registry.register(
            "storage.purge",
            self._purge_database_command,
            description="Clear the entire database.",
            aliases=["s.purge"],
        )
        registry.register(
            "storage.sql",
            self._execute_sql,
            description="Execute SQL command.",
            aliases=["s.sql"],
        )
        registry.register(
            "storage.export",
            self._export_table,
            description="Export a table to a CSV file.",
            example="storage.export my_table",
            aliases=["s.export"],
        )

    def set_database(self, database_path: str) -> None:
        if os.path.isdir(database_path):
            raise IsADirectoryError(f"Database path '{database_path}' is a directory.")

        if self.con:
            self.con.close()

        self.database_file = database_path
        self.con = sqlite3.connect(database_path)
        self.cur = self.con.cursor()

    def _validate_table_name(self, name: str) -> str:
        cleaned_name = "".join(c for c in name if c.isidentifier()).lstrip("_")
        if not cleaned_name or not cleaned_name.isidentifier():
            raise ValueError(f"Invalid table name: '{name}'")
        return cleaned_name

    def create_table(self, name: str, columns: list[str]) -> None:
        if not self.con or not self.cur:
            raise sqlite3.OperationalError("Database connection is not available.")

        safe_name = self._validate_table_name(name)
        safe_columns = [self._validate_table_name(c) for c in columns]

        query = f"CREATE TABLE IF NOT EXISTS {safe_name} ({', '.join(f'{c} TEXT' for c in safe_columns)})"
        self.cur.execute(query)
        self.con.commit()

    def delete_table(self, name: str) -> None:
        if not self.con or not self.cur:
            raise sqlite3.OperationalError("Database connection is not available.")

        safe_name = self._validate_table_name(name)
        self.cur.execute(f"DROP TABLE IF EXISTS {safe_name}")
        self.con.commit()

    def purge_database(self) -> None:
        tables = self.get_tables()
        for table in tables:
            self.delete_table(table.name)

    def get_tables(self) -> list[Table]:
        if not self.con or not self.cur:
            raise sqlite3.OperationalError("Database connection is not available.")

        self.cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        table_names = [row[0] for row in self.cur.fetchall()]

        tables = []
        for name in table_names:
            safe_name = self._validate_table_name(name)
            self.cur.execute(f"PRAGMA table_info({safe_name})")
            columns = [col[1] for col in self.cur.fetchall()]

            self.cur.execute(f"SELECT COUNT(*) FROM {safe_name}")
            count = self.cur.fetchone()[0]
            tables.append(Table(name, columns, count))

        return tables

    def save(self, table: str, data: list[dict[str, any]]) -> None:
        if not data:
            return

        if not self.con or not self.cur:
            raise sqlite3.OperationalError("Database connection is not available.")

        safe_table = self._validate_table_name(table)
        columns = list(data[0].keys())
        safe_columns = [self._validate_table_name(c) for c in columns]

        placeholders = ", ".join(["?"] * len(safe_columns))
        query = f"INSERT INTO {safe_table} ({', '.join(safe_columns)}) VALUES ({placeholders})"

        values = [tuple(row.values()) for row in data]
        self.cur.executemany(query, values)
        self.con.commit()

    def _help(self) -> None:
        print(
            "Storage: Manages the database connection and data.\n\n"
            "Current configuration:\n"
            f"  - Database: {self.database_file}\n"
        )
        print("Available storage commands:")
        for command in registry.all_commands():
            if command.name.startswith("storage."):
                print(f"  {command}")

    def _reload(self) -> None:
        self.set_database(self.database_file)
        print("Database connection reloaded.")

    def _set_database(self, path: str) -> None:
        self.set_database(path)
        print(f"Database file set to '{path}'")

    def _delete_table(self, name: str) -> None:
        self.delete_table(name)
        print(f"Deleted table '{name}'.")

    def _purge_database_command(self) -> None:
        if (
            input("Are you sure you want to clear the entire database? (y/n): ")
            .lower()
            .strip()
            == "y"
        ):
            self.purge_database()
            print("Database purged.")
        else:
            print("Purge cancelled.")

    def _list_tables(self) -> None:
        tables = self.get_tables()
        if not tables:
            print("No tables found.")
            return

        print(f"{len(tables)} tables found:")
        for table in tables:
            cols = ", ".join(table.columns)
            print(f"  - {table.name} ({cols}): {table.count} rows")

    def _execute_sql(self, *st) -> None:
        if not self.con or not self.cur:
            raise sqlite3.OperationalError("Database connection is not available.")

        try:
            self.cur.execute(" ".join(st))
            self.con.commit()
            print(self.cur.fetchall())
        except sqlite3.Error as e:
            print(f"error: {e}")

    def _export_table(self, table_name: str) -> None:
        if not self.con or not self.cur:
            raise sqlite3.OperationalError("Database connection is not available.")

        table = next((t for t in self.get_tables() if t.name == table_name), None)
        if not table:
            print(f"error: table '{table_name}' not found.")
            return

        selected_columns = select_options(
            table.columns, title=f"Select columns to export from '{table_name}':"
        )

        if not selected_columns:
            print("Export cancelled: no columns selected.")
            return

        while True:
            prompt = f"How many rows to export? (all/{table.count}, or 'cancel'): "
            limit_str = input(prompt).strip().lower()

            if limit_str in ("cancel", "c"):
                print("Export cancelled.")
                return

            if limit_str == "all" or limit_str == "":
                limit = -1
                break
            try:
                limit = int(limit_str)
                if limit < 0:
                    raise ValueError
                break
            except ValueError:
                print(
                    "Invalid input. Please enter a positive number, 'all', or 'cancel'."
                )

        default_filename = f"{table_name}.csv"
        filename_prompt = f"Enter filename for export (default: {default_filename}): "
        output_filename = input(filename_prompt).strip()
        if not output_filename:
            output_filename = default_filename

        if not output_filename.lower().endswith(".csv"):
            output_filename += ".csv"

        safe_table_name = self._validate_table_name(table_name)
        safe_columns = [self._validate_table_name(c) for c in selected_columns]
        columns_str = ", ".join(safe_columns)

        query = f"SELECT {columns_str} FROM {safe_table_name}"
        if limit != -1:
            query += f" LIMIT {limit}"

        self.cur.execute(query)

        try:
            with open(output_filename, "w", newline="", encoding="utf-8") as csvfile:
                csv_writer = csv.writer(csvfile)
                csv_writer.writerow(selected_columns)
                csv_writer.writerows(self.cur.fetchall())

            row_count_str = "all" if limit == -1 else str(limit)
            print(f"Successfully exported {row_count_str} rows to '{output_filename}'")

        except IOError as e:
            print(f"error: Could not write to file '{output_filename}': {e}")
