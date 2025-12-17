import csv
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from tabulate import tabulate

from .registry import registry
from .termutils import err_print, select_options


@dataclass
class Table:
    name: str
    columns: list[str]
    count: int


class Storage:
    """manages database connection and data operations"""

    def __init__(self, database_path: str):
        self.con: sqlite3.Connection | None = None
        self.cur: sqlite3.Cursor | None = None
        self.database_file: str = ""
        self.set_database(database_path)
        self._register_commands()

    def _register_commands(self) -> None:
        """registers storage-related commands with the global registry"""
        registry.register(
            name="db",
            handler=self._set_database,
            description="set database file",
            example="db /path/to/database.db",
        )
        registry.register(
            name="tables",
            handler=self._list_tables,
            description="list all tables in the database",
            aliases=["list"],
        )
        registry.register(
            name="delete",
            handler=self._delete_table,
            description="delete a table",
            example="delete my_table",
            aliases=["del"],
        )
        registry.register(
            name="purge",
            handler=self._purge_database_command,
            description="clear the entire database",
        )
        registry.register(
            name="sql",
            handler=self._execute_sql,
            description="execute sql command",
            aliases=["execute"],
        )
        registry.register(
            name="export",
            handler=self._export_table,
            description="export a table to a csv file",
            example="export my_table",
        )
        registry.register(
            name="search",
            handler=self._search_command,
            description="search for a value in a table or all tables",
            example="search 'John' users",
            aliases=["find"],
        )

    def set_database(self, database_path: str) -> None:
        """sets the database file and establishes a connection"""
        if os.path.isdir(database_path):
            raise IsADirectoryError(f"database path '{database_path}' is a directory")

        if self.con:
            self.con.close()

        self.database_file = database_path
        self.con = sqlite3.connect(database_path)
        self.con.row_factory = sqlite3.Row  # improve row access
        self.cur = self.con.cursor()

    def create_table(self, name: str, columns: list[str]) -> None:
        """creates a new table in the database with specified columns"""
        if not self.con or not self.cur:
            raise sqlite3.OperationalError("database connection is not available")

        safe_name = self._validate_table_name(name)
        safe_columns = [self._validate_table_name(c) for c in columns]

        query = f'CREATE TABLE IF NOT EXISTS "{safe_name}" ({", ".join(f'"{c}" TEXT' for c in safe_columns)})'
        self.cur.execute(query)
        self.con.commit()

    def delete_table(self, name: str) -> None:
        """deletes a table from the database"""
        if not self.con or not self.cur:
            raise sqlite3.OperationalError("database connection is not available")

        safe_name = self._validate_table_name(name)
        self.cur.execute(f'DROP TABLE IF EXISTS "{safe_name}"')
        self.con.commit()

    def purge_database(self) -> None:
        """deletes all tables from the database"""
        tables = self.get_tables()
        for table in tables:
            self.delete_table(table.name)

    def get_tables(self) -> list[Table]:
        """retrieves a list of all tables in the database with their columns and row counts"""
        if not self.con or not self.cur:
            raise sqlite3.OperationalError("database connection is not available")

        self.cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        table_names = [row["name"] for row in self.cur.fetchall()]

        tables = []
        for name in table_names:
            safe_name = self._validate_table_name(name)
            self.cur.execute(f'PRAGMA table_info("{safe_name}")')
            columns = [col["name"] for col in self.cur.fetchall()]

            self.cur.execute(f'SELECT COUNT(*) FROM "{safe_name}"')
            count = self.cur.fetchone()[0]
            tables.append(Table(name, columns, count))

        return tables

    def save(self, table: str, data: list[dict[str, Any]]) -> None:
        """saves a list of dictionaries as rows into the specified table"""
        if not data:
            return

        if not self.con or not self.cur:
            raise sqlite3.OperationalError("database connection is not available")

        safe_table = self._validate_table_name(table)
        columns = list(data[0].keys())
        safe_columns = [self._validate_table_name(c) for c in columns]

        placeholders = ", ".join(["?"] * len(safe_columns))
        query = f'INSERT INTO "{safe_table}" ({", ".join(f'"{c}"' for c in safe_columns)}) VALUES ({placeholders})'

        values = [tuple(row.get(c, None) for c in columns) for row in data]
        self.cur.executemany(query, values)
        self.con.commit()

    def search_data(
        self, value: str, table_name: str | None = None
    ) -> dict[str, list[dict]]:
        """searches for a value across specified tables or all tables"""
        if not self.con or not self.cur:
            raise sqlite3.OperationalError("database connection is not available")

        tables_to_search = []
        if table_name:
            table = next((t for t in self.get_tables() if t.name == table_name), None)
            if not table:
                raise ValueError(f"table '{table_name}' not found")
            tables_to_search.append(table)
        else:
            tables_to_search = self.get_tables()

        search_pattern = f"%{value}%"
        all_results = {}

        for table in tables_to_search:
            if not table.columns:
                continue

            where_clause = " or ".join(f'"{col}" like ?' for col in table.columns)
            query = f'select * from "{table.name}" where {where_clause}'
            params = [search_pattern] * len(table.columns)

            self.cur.execute(query, params)
            rows = self.cur.fetchall()

            if rows:
                results = [dict(row) for row in rows]
                all_results[table.name] = results

        return all_results

    def _validate_table_name(self, name: str) -> str:
        """validates and sanitizes a table or column name for sql usage"""
        cleaned_name = "".join(c for c in name if c.isidentifier()).lstrip("_")
        if not cleaned_name or not cleaned_name.isidentifier():
            raise ValueError(f"invalid table name: '{name}'")
        return cleaned_name

    def _set_database(self, path: str) -> None:
        """sets the active database file"""
        self.set_database(path)
        print(f"database file set to '{path}'")

    def _delete_table(self, name: str) -> None:
        """deletes a specified table from the database"""
        self.delete_table(name)
        print(f"deleted table '{name}'")

    def _purge_database_command(self) -> None:
        """interactively prompts to clear the entire database"""
        prompt = "are you sure you want to clear the entire database? (y/n): "
        user_input = input(prompt).strip().lower()
        if user_input not in ("n", "no"):
            self.purge_database()
            print("database purged")
        else:
            print("purge cancelled")

    def _list_tables(self) -> None:
        """lists all tables in the database with their column and row counts"""
        tables = self.get_tables()
        if not tables:
            err_print("no tables found")
            return

        print(f"{len(tables)} tables found:")
        for table in tables:
            if table.columns:
                cols_str = ", ".join(table.columns)
                print(f"  - {table.name} ({cols_str}): {table.count} rows")
            else:
                print(f"  - {table.name}: {table.count} rows")

    def _execute_sql(self, *sql_parts: str) -> None:
        """executes an sql command and displays results if any"""
        if not self.con or not self.cur:
            raise sqlite3.OperationalError("database connection is not available")

        try:
            self.cur.execute(" ".join(sql_parts))
            self.con.commit()
            results = self.cur.fetchall()
            if results:
                print(
                    tabulate(
                        [dict(row) for row in results], headers="keys", tablefmt="grid"
                    )
                )
            else:
                print("query executed successfully, no results to display")
        except sqlite3.Error as e:
            err_print(str(e))

    def _export_table(self, table_name: str) -> None:
        """exports a specified table to a csv file"""
        if not self.con or not self.cur:
            raise sqlite3.OperationalError("database connection is not available")

        table = next((t for t in self.get_tables() if t.name == table_name), None)
        if not table:
            err_print(f"table '{table_name}' not found")
            return

        selected_columns = select_options(
            table.columns, title=f"select columns to export from '{table_name}'"
        )

        if not selected_columns:
            err_print("export cancelled: no columns selected")
            return

        while True:
            prompt = f"how many rows to export? (all/{table.count}, or 'cancel'): "
            limit_str = input(prompt).strip().lower()

            if limit_str in ("cancel", "c"):
                err_print("export cancelled")
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
                err_print(
                    "invalid input, please enter a positive number, 'all', or 'cancel'"
                )

        default_filename = f"{table_name}.csv"
        filename_prompt = f"enter filename for export (default: {default_filename}): "
        output_filename = input(filename_prompt).strip()
        if not output_filename:
            output_filename = default_filename

        if not output_filename.lower().endswith(".csv"):
            output_filename += ".csv"

        safe_table_name = self._validate_table_name(table_name)
        safe_columns = [self._validate_table_name(c) for c in selected_columns]
        columns_str = ", ".join(f'"{c}"' for c in safe_columns)

        query = f'SELECT {columns_str} FROM "{safe_table_name}"'
        if limit != -1:
            query += f" LIMIT {limit}"

        self.cur.execute(query)

        try:
            with open(output_filename, "w", newline="", encoding="utf-8") as csvfile:
                csv_writer = csv.writer(csvfile)
                csv_writer.writerow(selected_columns)
                csv_writer.writerows(self.cur.fetchall())

            row_count_str = "all" if limit == -1 else str(limit)
            print(f"successfully exported {row_count_str} rows to '{output_filename}'")

        except IOError as e:
            err_print(f"could not write to file '{output_filename}': {e}")

    def _search_command(self, *args: str) -> None:
        """searches for a value in a table or all tables and displays the results"""
        if not args:
            err_print("search value cannot be empty")
            return

        value = args[0]
        table_name = args[1] if len(args) > 1 else None

        print(f"searching for '{value}'...")
        start_time = time.time()
        try:
            results_by_table = self.search_data(value, table_name)
        except (ValueError, sqlite3.OperationalError) as e:
            err_print(str(e))
            return
        end_time = time.time()

        total_matches = 0
        if not results_by_table:
            print("no matches found")
            return

        for table, rows in results_by_table.items():
            total_matches += len(rows)
            print(f"\nfound {len(rows)} match(es) in table '{table}':")
            print(tabulate(rows, headers="keys", tablefmt="grid"))

        duration = end_time - start_time
        print(f"\nfound {total_matches} total match(es) in {duration:.4f} seconds")
