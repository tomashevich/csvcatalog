import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Table:
    name: str
    columns: list[str]
    count: int


class BaseStorage(ABC):
    """abstract base class for storage operations"""

    @abstractmethod
    def create_table(self, name: str, columns: list[str]) -> None: ...

    @abstractmethod
    def delete_table(self, name: str) -> None: ...

    @abstractmethod
    def purge_database(self) -> None: ...

    @abstractmethod
    def get_table(self, name: str) -> Table | None: ...

    @abstractmethod
    def get_tables(self) -> list[Table]: ...

    @abstractmethod
    def save(self, table: str, data: list[dict[str, Any]]) -> None: ...

    @abstractmethod
    def search(
        self, value: str, targets: list[str] | None = None
    ) -> dict[str, list[dict[str, Any]]]: ...

    @abstractmethod
    def sql(self, query: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def close(self) -> None: ...


class SqliteStorage(BaseStorage):
    """manages database connection and data operations for sqlite"""

    def __init__(self, database_path: Path):
        self._db_path = database_path
        self.con = sqlite3.connect(database_path)
        self.con.row_factory = sqlite3.Row
        self.cur = self.con.cursor()

    def create_table(self, name: str, columns: list[str]) -> None:
        """creates a new table in the database with specified columns"""
        query = f'CREATE TABLE IF NOT EXISTS "{name}" ({", ".join(f'"{c}" TEXT' for c in columns)})'
        self.cur.execute(query)
        self.con.commit()

    def delete_table(self, name: str) -> None:
        """deletes a table from the database"""
        self.cur.execute(f'DROP TABLE IF EXISTS "{name}"')
        self.con.commit()

    def purge_database(self) -> None:
        """deletes all tables from the database"""
        tables = self.get_tables()
        for table in tables:
            self.delete_table(table.name)

    def get_table(self, name: str) -> Table | None:
        """retrieves metadata for a single table"""
        self.cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        )
        if not self.cur.fetchone():
            return None

        self.cur.execute(f'PRAGMA table_info("{name}")')
        columns = [col["name"] for col in self.cur.fetchall()]

        self.cur.execute(f'SELECT COUNT(*) FROM "{name}"')
        count = self.cur.fetchone()[0]
        return Table(name, columns, count)

    def get_tables(self) -> list[Table]:
        """retrieves a list of all tables in the database with their columns and row counts"""
        self.cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        table_names = [row["name"] for row in self.cur.fetchall()]

        tables = []
        for name in table_names:
            self.cur.execute(f'PRAGMA table_info("{name}")')
            columns = [col["name"] for col in self.cur.fetchall()]

            self.cur.execute(f'SELECT COUNT(*) FROM "{name}"')
            count = self.cur.fetchone()[0]
            tables.append(Table(name, columns, count))

        return tables

    def save(self, table: str, data: list[dict[str, Any]]) -> None:
        """saves a list of dictionaries as rows into the specified table"""
        if not data:
            return

        columns = list(data[0].keys())
        placeholders = ", ".join(["?"] * len(columns))
        query = f'INSERT INTO "{table}" ({", ".join(f'"{c}"' for c in columns)}) VALUES ({placeholders})'

        values = [tuple(row.get(c, None) for c in columns) for row in data]
        self.cur.executemany(query, values)
        self.con.commit()

    def search(
        self, value: str, targets: list[str] | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        """searches for a value in the database across specified targets"""
        if not targets:
            targets = [t.name for t in self.get_tables()]

        search_pattern = f"%{value}%"

        all_tables_map = None  # lazy load

        select_queries = []
        all_params = []

        for target in targets:
            table_name: str | None = None
            column_name: str | None = None

            if "." in target:
                table_name, column_name = target.split(".", 1)
            else:
                table_name = target

            tables_to_search = []
            if table_name == "*":
                if all_tables_map is None:
                    all_tables_map = {t.name: t for t in self.get_tables()}
                tables_to_search = list(all_tables_map.values())
            else:
                table = self.get_table(table_name)
                if not table:
                    continue
                tables_to_search = [table]

            for t in tables_to_search:
                columns_to_search = []
                if column_name:
                    if column_name == "*":
                        columns_to_search = t.columns
                    elif column_name in t.columns:
                        columns_to_search.append(column_name)
                else:
                    columns_to_search = t.columns

                if not columns_to_search:
                    continue

                # need to select all columns for UNIONs, but can do it more good that it shit
                all_cols_select = ", ".join(f'"{c}"' for c in t.columns)
                where_clause = " OR ".join(f'"{c}" LIKE ?' for c in columns_to_search)

                query = f"SELECT '{t.name}' as source_table, {all_cols_select} FROM \"{t.name}\" WHERE {where_clause}"
                select_queries.append(query)
                all_params.extend([search_pattern] * len(columns_to_search))

        if not select_queries:
            return {}

        full_query = " UNION ALL ".join(select_queries)

        all_results: dict[str, list[dict[str, Any]]] = {}
        seen_rows_by_table: dict[str, set[tuple]] = {}

        try:
            self.cur.execute(full_query, all_params)
            rows = self.cur.fetchall()

            for row in rows:
                row_dict = dict(row)
                source_table = row_dict.pop("source_table")

                if source_table not in all_results:
                    all_results[source_table] = []
                    seen_rows_by_table[source_table] = set()

                # for hashable row
                row_tuple = tuple(row_dict.items())
                if row_tuple not in seen_rows_by_table[source_table]:
                    all_results[source_table].append(row_dict)
                    seen_rows_by_table[source_table].add(row_tuple)

        except sqlite3.Error as e:
            print(f"error during search: {e}")

        return all_results

    def sql(self, query: str) -> list[dict[str, Any]]:
        """executes a raw sql query"""
        self.cur.execute(query)
        rows = self.cur.fetchall()
        self.con.commit()
        return [dict(row) for row in rows]

    def close(self) -> None:
        """closes the database connection"""
        if self.con:
            self.con.close()
