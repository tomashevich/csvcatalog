import json
import re
import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast, override

# a simple regex to validate table/column names
META_TABLE_NAME = "_csvcatalog_meta_"

# the subset of python values that sqlite can store directly
SqlValue = str | int | float | bytes | None


def sanitize_identifier(identifier: str) -> str:
    """replaces invalid characters with underscores to create a valid sql identifier"""
    # since all identifiers are quoted in queries, the only truly problematic
    # character is the double quote itself.
    return identifier.replace('"', "_")


def _validate_identifier(identifier: str) -> None:
    """raises valueerror if the identifier is not valid and safe"""
    if '"' in identifier:
        raise ValueError(f'invalid identifier: "{identifier}" contains double quotes')


@dataclass
class Table:
    name: str
    columns: list[str]
    count: int
    created_at: str
    description: str | None


def _row_value(row: sqlite3.Row, key: str) -> object:
    """returns a value from a sqlite row without leaking ``Any`` to callers"""
    return cast(object, row[key])


def _row_to_table(row: sqlite3.Row) -> Table:
    """converts a metadata row into a :class:`Table` instance"""
    columns = cast(list[str], json.loads(cast(str, _row_value(row, "columns"))))
    return Table(
        name=cast(str, _row_value(row, "table_name")),
        columns=columns,
        count=cast(int, _row_value(row, "row_count")),
        created_at=cast(str, _row_value(row, "created_at")),
        description=cast(str | None, _row_value(row, "description")),
    )


def _row_to_dict(row: sqlite3.Row) -> dict[str, SqlValue]:
    """converts a sqlite row into a regular dictionary"""
    return {key: cast(SqlValue, _row_value(row, key)) for key in row.keys()}


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
    def get_tables(
        self,
        description_filter: str | None = None,
        min_rows: int | None = None,
        created_after: str | None = None,
        sort_by: str | None = None,
    ) -> list[Table]: ...

    @abstractmethod
    def save(self, table: str, data: Sequence[Mapping[str, SqlValue]]) -> None: ...

    @abstractmethod
    def update_description(self, table_name: str, description: str) -> None: ...

    @abstractmethod
    def rename_table(self, old_name: str, new_name: str) -> None: ...

    @abstractmethod
    def update_created_at(self, table_name: str, new_date: str) -> None: ...

    @abstractmethod
    def search(
        self, value: str, targets: list[str] | None = None
    ) -> dict[str, list[dict[str, SqlValue]]]: ...

    @abstractmethod
    def sql(
        self, query: str, params: Sequence[SqlValue] | None = None
    ) -> list[dict[str, SqlValue]]: ...

    @abstractmethod
    def close(self) -> None: ...


class SqliteStorage(BaseStorage):
    """manages database connection and data operations for sqlite"""

    def __init__(self, database_path: Path):
        self._db_path: Path = database_path
        self.con: sqlite3.Connection = sqlite3.connect(database_path)
        self.con.row_factory = sqlite3.Row
        self.cur: sqlite3.Cursor = self.con.cursor()
        self._init_meta_table()

        def regexp(expr: str, item: object) -> bool:
            if item is None:
                return False
            reg = re.compile(expr)
            return reg.search(str(item)) is not None

        self.con.create_function("REGEXP", 2, regexp)

    @override
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
        _ = self.cur.execute(query)
        self.con.commit()

    @override
    def create_table(self, name: str, columns: list[str]) -> None:
        """creates a new table and registers it in the metadata table"""
        _validate_identifier(name)
        for col in columns:
            _validate_identifier(col)

        query = f'CREATE TABLE IF NOT EXISTS "{name}" ({", ".join(f'"{c}" TEXT' for c in columns)})'
        _ = self.cur.execute(query)

        meta_query = f"""
        INSERT OR REPLACE INTO "{META_TABLE_NAME}" (table_name, columns, row_count, created_at)
        VALUES (?, ?, 0, ?)
        """
        now = datetime.now(UTC).isoformat()
        _ = self.cur.execute(meta_query, (name, json.dumps(columns), now))
        self.con.commit()

    @override
    def delete_table(self, name: str) -> None:
        """deletes a table and its metadata entry"""
        _validate_identifier(name)
        _ = self.cur.execute(f'DROP TABLE IF EXISTS "{name}"')
        _ = self.cur.execute(
            f'DELETE FROM "{META_TABLE_NAME}" WHERE table_name = ?', (name,)
        )
        self.con.commit()
        _ = self.cur.execute("VACUUM")

    @override
    def purge_database(self) -> None:
        """deletes all user tables and clears the metadata table"""
        tables = self.get_tables()
        for table in tables:
            _ = self.cur.execute(f'DROP TABLE IF EXISTS "{table.name}"')
        _ = self.cur.execute(f'DELETE FROM "{META_TABLE_NAME}"')
        self.con.commit()
        _ = self.cur.execute("VACUUM")

    @override
    def get_table(self, name: str) -> Table | None:
        """retrieves metadata for a single table from the meta table"""
        _validate_identifier(name)
        _ = self.cur.execute(
            f'SELECT * FROM "{META_TABLE_NAME}" WHERE table_name = ?', (name,)
        )
        row = cast(sqlite3.Row | None, cast(object, self.cur.fetchone()))
        if not row:
            return None
        return _row_to_table(row)

    @override
    def get_tables(
        self,
        description_filter: str | None = None,
        min_rows: int | None = None,
        created_after: str | None = None,
        sort_by: str | None = None,
    ) -> list[Table]:
        """retrieves a list of all tables from the meta table with optional filters and sorting"""
        query = f'SELECT * FROM "{META_TABLE_NAME}"'
        where_clauses: list[str] = []
        params: list[SqlValue] = []

        if description_filter:
            where_clauses.append("description LIKE ?")
            params.append(f"%{description_filter}%")
        if min_rows is not None:
            where_clauses.append("row_count >= ?")
            params.append(min_rows)
        if created_after:
            where_clauses.append("created_at >= ?")
            params.append(created_after)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        if sort_by == "rows":
            query += " ORDER BY row_count ASC"
        elif sort_by == "date":
            query += " ORDER BY created_at ASC"
        else:
            query += " ORDER BY table_name ASC"

        _ = self.cur.execute(query, params)
        rows = cast(list[sqlite3.Row], cast(object, self.cur.fetchall()))
        return [_row_to_table(row) for row in rows]

    @override
    def save(self, table: str, data: Sequence[Mapping[str, SqlValue]]) -> None:
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
        _ = self.cur.executemany(query, values)

        # update row count
        _ = self.cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        count_row = cast(sqlite3.Row, cast(object, self.cur.fetchone()))
        count = cast(int, cast(object, count_row[0]))
        _ = self.cur.execute(
            f'UPDATE "{META_TABLE_NAME}" SET row_count = ? WHERE table_name = ?',
            (count, table),
        )
        self.con.commit()

    @override
    def update_description(self, table_name: str, description: str) -> None:
        """updates the description for a given table in the metadata"""
        _validate_identifier(table_name)
        _ = self.cur.execute(
            f'UPDATE "{META_TABLE_NAME}" SET description = ? WHERE table_name = ?',
            (description, table_name),
        )
        self.con.commit()

    @override
    def rename_table(self, old_name: str, new_name: str) -> None:
        """renames a table and updates its metadata record"""
        _validate_identifier(old_name)
        _validate_identifier(new_name)

        try:
            # get old metadata
            meta_row = cast(
                sqlite3.Row | None,
                cast(
                    object,
                    self.cur.execute(
                        f'SELECT * FROM "{META_TABLE_NAME}" WHERE table_name = ?',
                        (old_name,),
                    ).fetchone(),
                ),
            )
            if not meta_row:
                raise ValueError(f"table '{old_name}' not found in metadata")

            # rename actual table
            _ = self.cur.execute(f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"')

            # create new metadata record
            meta_query = f"""
            INSERT INTO "{META_TABLE_NAME}" (table_name, columns, row_count, created_at, description)
            VALUES (?, ?, ?, ?, ?)
            """
            _ = self.cur.execute(
                meta_query,
                (
                    new_name,
                    cast(str, _row_value(meta_row, "columns")),
                    cast(int, _row_value(meta_row, "row_count")),
                    cast(str, _row_value(meta_row, "created_at")),
                    cast(str | None, _row_value(meta_row, "description")),
                ),
            )

            # delete old metadata record
            _ = self.cur.execute(
                f'DELETE FROM "{META_TABLE_NAME}" WHERE table_name = ?', (old_name,)
            )

            self.con.commit()
        except Exception as e:
            self.con.rollback()
            raise e

    @override
    def update_created_at(self, table_name: str, new_date: str) -> None:
        """updates the created_at timestamp for a given table in the metadata"""
        _validate_identifier(table_name)
        _ = self.cur.execute(
            f'UPDATE "{META_TABLE_NAME}" SET created_at = ? WHERE table_name = ?',
            (new_date, table_name),
        )
        self.con.commit()

    @override
    def search(
        self, value: str, targets: list[str] | None = None
    ) -> dict[str, list[dict[str, SqlValue]]]:
        """searches for a value in the database across specified targets"""
        if not targets:
            targets = [t.name for t in self.get_tables()]

        search_pattern = f"%{value}%"
        all_results: dict[str, list[dict[str, SqlValue]]] = {}
        all_tables_map: dict[str, Table] | None = None  # lazy load

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

                    _ = self.cur.execute(query, params)
                    rows = cast(list[sqlite3.Row], cast(object, self.cur.fetchall()))

                    if not rows:
                        continue

                    if t.name not in all_results:
                        all_results[t.name] = []

                    all_results[t.name].extend(_row_to_dict(row) for row in rows)

                except sqlite3.Error as e:
                    print(f"error searching in table {t.name}: {e}")
                    continue  # continue to next table even if one fails

        return all_results

    @override
    def sql(
        self, query: str, params: Sequence[SqlValue] | None = None
    ) -> list[dict[str, SqlValue]]:
        """executes a raw sql query"""
        if params is None:
            params = []
        _ = self.cur.execute(query, params)
        rows = cast(list[sqlite3.Row], cast(object, self.cur.fetchall()))
        self.con.commit()
        return [_row_to_dict(row) for row in rows]

    @override
    def close(self) -> None:
        """closes the database connection"""
        if self.con:
            self.con.close()
