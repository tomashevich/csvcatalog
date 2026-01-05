import json
import re
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# a simple regex to validate table/column names
IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
META_TABLE_NAME = "_csvcatalog_meta_"


def sanitize_identifier(identifier: str) -> str:
    """replaces invalid characters with underscores to create a valid sql identifier"""
    # replace any non-alphanumeric characters (except underscore) with an underscore
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", identifier)
    # if the first character is a digit, prepend an underscore
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized


def _validate_identifier(identifier: str):
    """raises valueerror if the identifier is not valid and safe"""
    if not IDENTIFIER_REGEX.match(identifier):
        raise ValueError(f"invalid identifier: '{identifier}'")


@dataclass
class Table:
    name: str
    columns: list[str]
    count: int
    created_at: str
    description: str | None


class BaseStorage(ABC):
    """abstract base class for storage operations"""

    @abstractmethod
    def _init_meta_table(self) -> None: ...

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
    def update_description(self, table_name: str, description: str) -> None: ...

    @abstractmethod
    def search(
        self, value: str, targets: list[str] | None = None
    ) -> dict[str, list[dict[str, Any]]]: ...

    @abstractmethod
    def sql(
        self, query: str, params: list[Any] | None = None
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def close(self) -> None: ...


class SqliteStorage(BaseStorage):
    """manages database connection and data operations for sqlite"""

    def __init__(self, database_path: Path):
        self._db_path = database_path
        self.con = sqlite3.connect(database_path)
        self.con.row_factory = sqlite3.Row
        self.cur = self.con.cursor()
        self._init_meta_table()

        def regexp(expr, item):
            if item is None:
                return False
            reg = re.compile(expr)
            return reg.search(str(item)) is not None

        self.con.create_function("REGEXP", 2, regexp)

    def _init_meta_table(self) -> None:
        """ensures the metadata table exists"""
        query = f"""
        CREATE TABLE IF NOT EXISTS "{META_TABLE_NAME}" (
            table_name TEXT PRIMARY KEY,
            columns TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            description TEXT
        )
        """
        self.cur.execute(query)
        self.con.commit()

    def create_table(self, name: str, columns: list[str]) -> None:
        """creates a new table and registers it in the metadata table"""
        _validate_identifier(name)
        for col in columns:
            _validate_identifier(col)

        query = f'CREATE TABLE IF NOT EXISTS "{name}" ({", ".join(f'"{c}" TEXT' for c in columns)})'
        self.cur.execute(query)

        meta_query = f"""
        INSERT OR REPLACE INTO "{META_TABLE_NAME}" (table_name, columns, row_count, created_at)
        VALUES (?, ?, 0, ?)
        """
        now = datetime.utcnow().isoformat()
        self.cur.execute(meta_query, (name, json.dumps(columns), now))
        self.con.commit()

    def delete_table(self, name: str) -> None:
        """deletes a table and its metadata entry"""
        _validate_identifier(name)
        self.cur.execute(f'DROP TABLE IF EXISTS "{name}"')
        self.cur.execute(
            f'DELETE FROM "{META_TABLE_NAME}" WHERE table_name = ?', (name,)
        )
        self.con.commit()
        self.cur.execute("VACUUM")

    def purge_database(self) -> None:
        """deletes all user tables and clears the metadata table"""
        tables = self.get_tables()
        for table in tables:
            self.cur.execute(f'DROP TABLE IF EXISTS "{table.name}"')
        self.cur.execute(f'DELETE FROM "{META_TABLE_NAME}"')
        self.con.commit()
        self.cur.execute("VACUUM")

    def get_table(self, name: str) -> Table | None:
        """retrieves metadata for a single table from the meta table"""
        _validate_identifier(name)
        self.cur.execute(
            f'SELECT * FROM "{META_TABLE_NAME}" WHERE table_name = ?', (name,)
        )
        row = self.cur.fetchone()
        if not row:
            return None
        return Table(
            name=row["table_name"],
            columns=json.loads(row["columns"]),
            count=row["row_count"],
            created_at=row["created_at"],
            description=row["description"],
        )

    def get_tables(self) -> list[Table]:
        """retrieves a list of all tables from the meta table"""
        self.cur.execute(f'SELECT * FROM "{META_TABLE_NAME}"')
        return [
            Table(
                name=row["table_name"],
                columns=json.loads(row["columns"]),
                count=row["row_count"],
                created_at=row["created_at"],
                description=row["description"],
            )
            for row in self.cur.fetchall()
        ]

    def save(self, table: str, data: list[dict[str, Any]]) -> None:
        """saves data to a table and updates the row count in metadata"""
        _validate_identifier(table)
        if not data:
            return

        columns = list(data[0].keys())
        for col in columns:
            _validate_identifier(col)

        placeholders = ", ".join(["?"] * len(columns))
        query = f'INSERT INTO "{table}" ({", ".join(f'"{c}"' for c in columns)}) VALUES ({placeholders})'

        values = [tuple(row.get(c, None) for c in columns) for row in data]
        self.cur.executemany(query, values)

        # update row count
        self.cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = self.cur.fetchone()[0]
        self.cur.execute(
            f'UPDATE "{META_TABLE_NAME}" SET row_count = ? WHERE table_name = ?',
            (count, table),
        )
        self.con.commit()

    def update_description(self, table_name: str, description: str) -> None:
        """updates the description for a given table in the metadata"""
        _validate_identifier(table_name)
        self.cur.execute(
            f'UPDATE "{META_TABLE_NAME}" SET description = ? WHERE table_name = ?',
            (description, table_name),
        )
        self.con.commit()

    def search(
        self, value: str, targets: list[str] | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        """searches for a value in the database across specified targets"""
        if not targets:
            targets = [t.name for t in self.get_tables()]

        search_pattern = f"%{value}%"
        all_results: dict[str, list[dict[str, Any]]] = {}
        all_tables_map = None  # lazy load

        for target in targets:
            _validate_identifier(target.split(".", 1)[0].replace("*", "all"))
            if "." in target:
                _validate_identifier(target.split(".", 1)[1].replace("*", "all"))
            table_name, column_name = (
                target.split(".", 1) if "." in target else (target, None)
            )

            if table_name == "*":
                if all_tables_map is None:
                    all_tables_map = {t.name: t for t in self.get_tables()}
                tables_to_search = list(all_tables_map.values())
            else:
                table = self.get_table(table_name)
                tables_to_search = [table] if table else []

            if not tables_to_search:
                continue

            for t in tables_to_search:
                if not column_name:
                    columns_to_search = t.columns
                elif column_name == "*":
                    columns_to_search = t.columns
                elif column_name in t.columns:
                    columns_to_search = [column_name]
                else:
                    columns_to_search = []

                if not columns_to_search:
                    continue

                # query each table individually to avoid union all errors
                try:
                    where_clause = " OR ".join(
                        f'"{c}" LIKE ?' for c in columns_to_search
                    )
                    query = f'SELECT * FROM "{t.name}" WHERE {where_clause}'
                    params = [search_pattern] * len(columns_to_search)

                    self.cur.execute(query, params)
                    rows = self.cur.fetchall()

                    if not rows:
                        continue

                    if t.name not in all_results:
                        all_results[t.name] = []

                    for row in rows:
                        all_results[t.name].append(dict(row))

                except sqlite3.Error as e:
                    print(f"error searching in table {t.name}: {e}")
                    continue  # continue to next table even if one fails

        return all_results

    def sql(self, query: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        """executes a raw sql query"""
        if params is None:
            params = []
        self.cur.execute(query, params)
        rows = self.cur.fetchall()
        self.con.commit()
        return [dict(row) for row in rows]

    def close(self) -> None:
        """closes the database connection"""
        if self.con:
            self.con.close()
