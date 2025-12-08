import os
import sqlite3
from dataclasses import dataclass

from src.cmd.command import Command


@dataclass
class Table:
    name: str
    columns: list[str]
    count: int


# warning: can be a sql injection attack. but we cant use placeholders for table names in query
class Saver:
    def __init__(self, database_path: str):
        self.con: sqlite3.Connection | None = None
        self.cur: sqlite3.Cursor | None = None
        self.database_file: str = ""
        self.set_database(database_path)

        self.commands = [
            Command(
                "saver.help",
                self.command_help_handler,
                description="display help",
                aliases=["s.help"],
            ),
            Command(
                "saver.reload",
                self.command_reload_handler,
                description="reload database connection",
                aliases=["s.reload"],
            ),
            Command(
                "saver.tables",
                self.command_tables_handler,
                description="list all tables in database",
                aliases=["s.tables"],
            ),
            Command(
                "saver.database",
                self.command_database_handler,
                description="set database file",
                example="s.db /path/to/database.db",
                aliases=["s.database", "s.db"],
            ),
            Command(
                "saver.delete.table",
                self.command_delete_table_handler,
                description="delete a table",
                example="s.del.table table_name",
                aliases=["s.delete.table", "s.del.table"],
            ),
        ]

    def set_database(self, database_path: str) -> None:
        if os.path.isdir(database_path):
            raise IsADirectoryError(f"Database file '{database_path}' is a directory")

        if not os.path.exists(database_path):
            with open(database_path, "w"):
                pass

        if self.con is not None or self.cur is not None:
            self.cur.close()
            self.con.close()

        self.database_file = database_path

        self.con = sqlite3.connect(self.database_file)
        self.cur = self.con.cursor()

    def create_table(self, name: str, columns: list[str]) -> None:
        if self.con is None or self.cur is None:
            raise Exception("Database file not opened")

        self.cur.execute(f"CREATE TABLE IF NOT EXISTS {name} ({', '.join(columns)})")
        res = self.cur.execute(f"SELECT name FROM sqlite_master WHERE name='{name}'")
        if res.fetchone() is None:
            raise Exception("Table creation failed")

    def delete_table(self, name: str) -> None:
        self.cur.execute(f"DROP TABLE IF EXISTS {name}")
        self.con.commit()

    def get_tables(self) -> list[Table]:
        if self.con is None or self.cur is None:
            raise Exception("Database file not opened")

        res = self.cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row[0] for row in res.fetchall()]

        table_info = []
        for table_name in tables:
            self.cur.execute(f"PRAGMA table_info('{table_name}');")
            columns = [col[1] for col in self.cur.fetchall()]

            res = self.cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = res.fetchone()[0]

            table_info.append(Table(table_name, columns, count))

        return table_info

    def save(self, table: str, data: list[dict[str, any]]) -> None:
        if self.con is None or self.cur is None:
            raise Exception("Database file not opened")

        columns = list(data[0].keys())
        placeholders = ", ".join(["?"] * len(columns))
        values = [tuple(row.values()) for row in data]

        self.cur.executemany(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        self.con.commit()

    #
    # Commands
    #
    def command_help_handler(self) -> None:
        print(
            f"""Saver help:
  Setup your database connections. View, edit, delete data inside.

Current vars:
  ex.database: {self.database_file}
            """
        )
        print("Available extractor commands:")
        for command in self.commands:
            print(f"  {command}")

    def command_reload_handler(self) -> None:
        self.set_database(self.database_file)
        print("reloaded!")

    def command_database_handler(self, *args) -> None:
        self.set_database(args[0])
        print(f"database file set to '{args[0]}'")

    def command_delete_table_handler(self, *args) -> None:
        self.delete_table(args[0])
        print(f"deleted '{args[0]}' table")

    def command_tables_handler(self) -> None:
        tables = self.get_tables()
        tables_len = len(tables)
        if tables_len == 0:
            print("no tables found")
            return

        print(f"{tables_len} tables:")
        for table in tables:
            print(f"  {table.name} ({', '.join(table.columns)}): {table.count} rows")
