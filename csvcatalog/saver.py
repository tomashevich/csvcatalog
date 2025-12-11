import os
import sqlite3
from dataclasses import dataclass
from .registry import registry


@dataclass
class Table:
    name: str
    columns: list[str]
    count: int


class Saver:
    def __init__(self, database_path: str):
        self.con: sqlite3.Connection | None = None
        self.cur: sqlite3.Cursor | None = None
        self.database_file: str = ""
        self.set_database(database_path)
        self._register_commands()

    def _register_commands(self) -> None:
        registry.register(
            "s.help",
            self._help,
            description="Display saver help.",
            aliases=["saver.help"],
        )
        registry.register(
            "s.reload",
            self._reload,
            description="Reload database connection.",
            aliases=["saver.reload"],
        )
        registry.register(
            "s.tables",
            self._list_tables,
            description="List all tables in the database.",
            aliases=["saver.tables"],
        )
        registry.register(
            "s.db",
            self._set_database,
            description="Set database file.",
            example="s.db /path/to/database.db",
            aliases=["saver.database"],
        )
        registry.register(
            "s.del.table",
            self._delete_table,
            description="Delete a table.",
            example="s.del.table my_table",
            aliases=["saver.delete.table"],
        )
        registry.register(
            "s.purge",
            self._purge_database_command,
            description="Clear the entire database.",
            aliases=["saver.purge"],
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
        cleaned_name = ''.join(c for c in name if c.isidentifier() or c in '_').lstrip('_')
        if not cleaned_name.isidentifier():
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
            "Saver: Manages the database connection and data.\n\n"
            "Current configuration:\n"
            f"  - Database: {self.database_file}\n"
        )
        print("Available saver commands:")
        for command in registry.all_commands():
            if command.name.startswith("s."):
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
        if input("Are you sure you want to clear the entire database? (y/n): ").lower().strip() == "y":
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
