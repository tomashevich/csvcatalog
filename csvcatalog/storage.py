import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Table:
    name: str
    columns: list[str]
    count: int


class Storage:
    """manages database connection and data operations"""

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
            # global search across all columns in all tables
            targets = [t.name for t in self.get_tables()]

        all_results: dict[str, list[dict[str, Any]]] = {}
        search_pattern = f"%{value}%"
        
        all_tables = None # lazy load

        for target in targets:
            table_name: str | None = None
            column_name: str | None = None

            if "." in target:
                table_name, column_name = target.split(".", 1)
            else:
                table_name = target
            
            if table_name == "*":
                if all_tables is None:
                    all_tables = self.get_tables()
                tables_to_search = all_tables
            else:
                table = self.get_table(table_name)
                if not table:
                    continue # Or raise error? For now, skip.
                tables_to_search = [table]

            for t in tables_to_search:
                columns_to_search = []
                if column_name:
                    if column_name in t.columns:
                        columns_to_search.append(column_name)
                else:
                    columns_to_search = t.columns
                
                if not columns_to_search:
                    continue

                query = f'SELECT * FROM "{t.name}" WHERE {" OR ".join(f'"{c}" LIKE ?' for c in columns_to_search)}'
                params = [search_pattern] * len(columns_to_search)
                
                try:
                    self.cur.execute(query, params)
                    rows = self.cur.fetchall()
                    if rows:
                        if t.name not in all_results:
                            all_results[t.name] = []
                        
                        # simple deduplication
                        for row in rows:
                            if dict(row) not in all_results[t.name]:
                                all_results[t.name].append(dict(row))

                except sqlite3.Error:
                    # ignore errors on a column not existing, etc.
                    continue
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
