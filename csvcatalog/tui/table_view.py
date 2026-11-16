import csv
from pathlib import Path
from typing import cast, final, override

from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, DataTable, Static

from .. import storage
from ..storage import BaseStorage, SqlValue
from .format import truncate
from .modals import (
    ConfirmModal,
    ExportSelectionModal,
    PageRequest,
    PaginationModal,
    RowEditModal,
    RowPatch,
    RowSearchModal,
    RowSearchResult,
)
from .selection import MultiSelectTable

DEFAULT_PAGE_SIZE = 100


@final
class TableEditorView(Vertical):
    """paged, searchable and editable view of a single table"""

    class CloseRequested(Message):
        table_name: str

        def __init__(self, table_name: str) -> None:
            self.table_name = table_name
            super().__init__()

    class TableChanged(Message):
        table_name: str

        def __init__(self, table_name: str) -> None:
            self.table_name = table_name
            super().__init__()

    class EditTableRequested(Message):
        table_name: str

        def __init__(self, table_name: str) -> None:
            self.table_name = table_name
            super().__init__()

    class DeleteTableRequested(Message):
        table_name: str

        def __init__(self, table_name: str) -> None:
            self.table_name = table_name
            super().__init__()

    class ExportTableRequested(Message):
        table_name: str

        def __init__(self, table_name: str) -> None:
            self.table_name = table_name
            super().__init__()

    def __init__(
        self,
        storage_instance: BaseStorage,
        table_name: str,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id, classes="table-editor")
        self.storage = storage_instance
        self.table_name = table_name
        self._columns: list[str] = []
        self._offset = 0
        self._total = 0
        self._page_rows = 0
        self._page_size = DEFAULT_PAGE_SIZE
        self._search = ""
        self._search_columns: list[str] | None = None
        self._pending_row_number: int | None = None
        self._sort_column: str | None = None
        self._sort_desc = False

    @override
    def compose(self) -> ComposeResult:
        with Horizontal(id="table-toolbar"):
            yield Button("+ Row", id="table-add", classes="compact-action accent")
            yield Button(
                "Edit table",
                id="table-edit",
                classes="compact-action",
                tooltip="Edit table metadata and columns",
            )
            yield Button(
                "Export",
                id="table-export",
                classes="compact-action",
                tooltip="Export this table to CSV",
            )
            yield Button(
                "Delete table",
                id="table-delete",
                classes="compact-action danger",
                tooltip="Delete this table and all of its rows",
            )
        yield MultiSelectTable(id="rows", cursor_type="row", zebra_stripes=True)
        yield Static("", id="rows-empty")
        with Horizontal(id="row-footer"):
            yield Button(
                "",
                id="row-range",
                classes="compact-action range-action",
                tooltip="Change page size or jump to a page / row",
            )
            yield Button(
                "Edit",
                id="row-edit",
                classes="compact-action",
                tooltip="Edit the selected row",
            )
            yield Button(
                "Export",
                id="row-export",
                classes="compact-action",
                tooltip="Export selected rows to CSV",
            )
            yield Button(
                "Delete",
                id="row-delete",
                classes="compact-action danger",
                tooltip="Delete selected rows",
            )
            yield Button("<", id="row-prev", classes="compact-action pager")
            yield Button(">", id="row-next", classes="compact-action pager")

    def on_mount(self) -> None:
        self._sync_actions()
        self.reload()
        _ = self._rows_widget().focus()

    def _sync_actions(self) -> None:
        table = self._rows_widget()
        selected = table.selected_keys
        multi = len(selected) > 1
        has_rows = table.row_count > 0
        width = (
            self.size.width if self.size.width > 20 else self._catalog_app().size.width
        )
        compact = width < 72
        edit_button = self.query_one("#row-edit", Button)
        export_button = self.query_one("#row-export", Button)
        delete_button = self.query_one("#row-delete", Button)
        table_export_button = self.query_one("#table-export", Button)
        table_export_button.label = "Export table" if width >= 90 else "Export"
        edit_button.display = not multi
        edit_button.disabled = not has_rows
        export_button.disabled = not has_rows
        delete_button.disabled = not has_rows
        edit_button.label = "Edit" if compact else "Edit row"
        export_button.label = (
            "Export" if compact else ("Export rows" if selected else "Export row")
        )
        delete_button.label = (
            "Delete" if compact else ("Delete rows" if selected else "Delete row")
        )
        edit_button.tooltip = (
            "Edit the selected row" if selected else "Edit the current row"
        )
        export_button.tooltip = (
            "Export selected rows to CSV"
            if selected
            else "Export the current row to CSV"
        )
        delete_button.tooltip = (
            "Delete selected rows" if selected else "Delete the current row"
        )
        _ = edit_button.refresh(layout=True)
        _ = export_button.refresh(layout=True)
        _ = delete_button.refresh(layout=True)
        _ = table_export_button.refresh(layout=True)

    @on(events.Resize)
    def _resized(self, event: events.Resize) -> None:
        _ = event
        self._sync_actions()
        self._apply_column_widths()
        self._update_footer(self._page_rows)

    @on(MultiSelectTable.SelectionChanged, "#rows")
    def _selection_changed(self, event: MultiSelectTable.SelectionChanged) -> None:
        _ = event
        self._sync_actions()
        self._update_footer(self._page_rows)

    def _rows_widget(self) -> MultiSelectTable:
        return self.query_one("#rows", MultiSelectTable)

    def _catalog_app(self) -> App[None]:
        return cast(App[None], self.app)

    def focus_rows(self) -> None:
        table = self._rows_widget()
        if table.display:
            _ = table.focus()
        else:
            _ = self.query_one("#table-add", Button).focus()

    def _table_columns(self) -> list[str]:
        table = self.storage.get_table(self.table_name)
        return [] if table is None else list(table.columns)

    def _rebuild_columns(self) -> None:
        table = self._rows_widget()
        _ = table.clear(columns=True)
        for column in self._columns:
            _ = table.add_column(
                Text(column),
                key=column,
                width=self._column_width(len(self._columns)),
            )
        self._apply_column_widths()
        self._update_sort_labels()

    def _column_width(self, column_count: int) -> int:
        width = (
            self.size.width if self.size.width > 20 else self._catalog_app().size.width
        )
        available = max(20, width - 8)
        # data cells add horizontal padding; leave room so no scrollbar appears
        return max(10, min(32, available // max(1, column_count) - 2))

    def _apply_column_widths(self) -> None:
        table = self._rows_widget()
        if not table.columns:
            return
        width = self._column_width(len(self._columns))
        for column in table.columns.values():
            column.width = width
        _ = table.refresh()

    def _update_sort_labels(self) -> None:
        table = self._rows_widget()
        for column_key, column in table.columns.items():
            key = column_key.value
            if not isinstance(key, str):
                continue
            label = key
            if key == self._sort_column:
                label += " ↓" if self._sort_desc else " ↑"
            column.label = Text(label)
        _ = table.refresh()

    def reload(self) -> None:
        """reload the current page from storage"""
        columns = self._table_columns()
        if not columns:
            self.notify("Table no longer exists", severity="error")
            _ = self.post_message(self.CloseRequested(self.table_name))
            return
        self._rows_widget().clear_selection()
        if columns != self._columns:
            self._columns = columns
            self._rebuild_columns()
        if self._sort_column is not None and self._sort_column not in self._columns:
            self._sort_column = None
            self._sort_desc = False

        rows, total = self.storage.get_rows(
            self.table_name,
            offset=self._offset,
            limit=self._page_size,
            search=self._search or None,
            search_columns=self._search_columns,
            sort_column=self._sort_column,
            sort_desc=self._sort_desc,
        )
        self._total = total
        if self._offset >= total and total > 0:
            self._offset = max(0, ((total - 1) // self._page_size) * self._page_size)
            rows, total = self.storage.get_rows(
                self.table_name,
                offset=self._offset,
                limit=self._page_size,
                search=self._search or None,
                search_columns=self._search_columns,
                sort_column=self._sort_column,
                sort_desc=self._sort_desc,
            )
            self._total = total

        table = self._rows_widget()
        _ = table.clear(columns=False)
        preview_width = max(1, self._column_width(len(self._columns)))
        for row in rows:
            rowid = row.get("__csvcatalog_rowid__")
            values = [
                Text(truncate(_preview(row.get(column)), preview_width))
                for column in self._columns
            ]
            _ = table.add_row(
                *values,
                key=str(rowid) if rowid is not None else None,
            )
        empty = self.query_one("#rows-empty", Static)
        if rows:
            table.display = True
            empty.display = False
            table.move_cursor(row=0, column=0, animate=False)
        else:
            table.display = False
            empty.display = True
            if self._search:
                empty.update(f"No rows match “{self._search}”")
            else:
                empty.update("This table is empty · use + Row to add the first row")
        self._page_rows = len(rows)
        if self._pending_row_number is not None and table.row_count:
            target = self._pending_row_number - 1 - self._offset
            table.move_cursor(
                row=max(0, min(target, table.row_count - 1)),
                column=0,
                animate=False,
            )
            self._pending_row_number = None
        self._update_footer(self._page_rows)
        self._update_sort_labels()
        self._sync_actions()

    @on(Button.Pressed, "#row-range")
    def _open_pagination(self) -> None:
        current_page = self._offset // max(1, self._page_size) + 1
        _ = self._catalog_app().push_screen(
            PaginationModal(
                self._total,
                self._page_size,
                current_page,
            ),
            self._apply_page_request,
        )

    def _apply_page_request(self, request: PageRequest | None) -> None:
        if request is None:
            return
        self._page_size = request.limit
        if request.row is not None:
            self._offset = ((request.row - 1) // self._page_size) * self._page_size
            self._pending_row_number = request.row
        else:
            self._offset = max(0, (request.page - 1) * self._page_size)
            self._pending_row_number = None
        self.reload()

    def _update_footer(self, page_rows: int) -> None:
        start = self._offset + 1 if self._total else 0
        end = min(self._offset + page_rows, self._total)
        width = (
            self.size.width if self.size.width > 20 else self._catalog_app().size.width
        )
        selected = self._rows_widget().selected_keys
        if selected:
            range_text = f"{len(selected):,} selected"
            if width >= 96:
                range_text += f" · {start:,}–{end:,} of {self._total:,}"
        elif self._total:
            if width < 72:
                range_text = f"{start:,}–{end:,}"
            else:
                range_text = f"{start:,}–{end:,} of {self._total:,}"
        else:
            range_text = "No matches" if self._search else "No rows"
        if self._search and self._total and width >= 72 and not selected:
            range_text += f" · “{self._search}”"
            if self._search_columns is not None and len(self._search_columns) < len(
                self._columns
            ):
                column_count = len(self._search_columns)
                range_text += (
                    f" in {column_count} {'column' if column_count == 1 else 'columns'}"
                )
        self.query_one("#row-range", Button).label = range_text
        self.query_one("#row-prev", Button).disabled = self._offset <= 0
        self.query_one("#row-next", Button).disabled = (
            self._offset + self._page_size >= self._total
        )

    def open_search(self) -> None:
        _ = self._catalog_app().push_screen(
            RowSearchModal(
                self._columns,
                self._search,
                self._search_columns,
            ),
            self._apply_search_result,
        )

    def _apply_search_result(self, result: RowSearchResult | None) -> None:
        if result is None:
            return
        if result.replace:
            try:
                rows, occurrences = self.storage.replace_in_columns(
                    self.table_name,
                    result.columns,
                    result.query,
                    result.replacement,
                )
            except Exception as e:
                self.notify(f"Could not replace text: {e}", severity="error")
                return
            self._search = result.query
            self._search_columns = result.columns
            self._pending_row_number = None
            self._offset = 0
            self.reload()
            occurrence_word = "occurrence" if occurrences == 1 else "occurrences"
            row_word = "row" if rows == 1 else "rows"
            self.notify(
                f"Replaced {occurrences:,} {occurrence_word} in {rows:,} {row_word}",
                severity="information",
            )
            return
        self._search = result.query
        self._search_columns = result.columns if result.query else None
        self._pending_row_number = None
        self._offset = 0
        self.reload()

    def has_search(self) -> bool:
        return bool(self._search)

    def has_selection(self) -> bool:
        return bool(self._rows_widget().selected_keys)

    def clear_selection(self) -> None:
        self._rows_widget().clear_selection()

    def clear_search(self) -> None:
        if not self._search:
            return
        self._search = ""
        self._search_columns = None
        self._pending_row_number = None
        self._offset = 0
        self.reload()

    @on(DataTable.HeaderSelected, "#rows")
    def _header_selected(self, event: DataTable.HeaderSelected) -> None:
        column = event.column_key.value
        if not isinstance(column, str) or column not in self._columns:
            return
        if column == self._sort_column:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_column = column
            self._sort_desc = False
        self._offset = 0
        self.reload()

    @on(DataTable.RowSelected, "#rows")
    def _row_selected(self, event: DataTable.RowSelected) -> None:
        if len(self._rows_widget().selected_keys) > 1:
            return
        row_key = event.row_key.value
        if isinstance(row_key, str):
            try:
                self._open_row_editor(int(row_key))
            except ValueError:
                return

    def _open_row_editor(self, rowid: int) -> None:
        row = self.storage.get_row(self.table_name, rowid)
        if row is None:
            self.notify("Row no longer exists", severity="warning")
            self.reload()
            return
        values = {column: _cell_text(row.get(column)) for column in self._columns}
        _ = self._catalog_app().push_screen(
            RowEditModal(
                self.table_name,
                self._columns,
                values,
                rowid=rowid,
            ),
            lambda patch: self._apply_row_patch(rowid, patch),
        )

    def edit_selected_row(self) -> None:
        if len(self._rows_widget().selected_keys) > 1:
            return
        rowid = self._selected_or_cursor_rowid()
        if rowid is not None:
            self._open_row_editor(rowid)

    @on(Button.Pressed, "#table-add")
    def _add_row(self) -> None:
        columns = self._table_columns()
        if not columns:
            return
        _ = self._catalog_app().push_screen(
            RowEditModal(self.table_name, columns, {}),
            lambda patch: self._apply_row_patch(None, patch),
        )

    def _apply_row_patch(self, rowid: int | None, patch: RowPatch | None) -> None:
        if patch is None:
            return
        try:
            if patch.delete and rowid is not None:
                self.storage.delete_row(self.table_name, rowid)
            elif rowid is None:
                self.storage.insert_row(self.table_name, patch.values)
            else:
                self.storage.update_row(self.table_name, rowid, patch.values)
        except Exception as e:
            self.notify(f"Could not save row: {e}", severity="error")
            return
        _ = self.post_message(self.TableChanged(self.table_name))
        self.reload()

    @on(Button.Pressed, "#row-prev")
    def _prev_page(self) -> None:
        self._offset = max(0, self._offset - self._page_size)
        self.reload()

    @on(Button.Pressed, "#row-next")
    def _next_page(self) -> None:
        if self._offset + self._page_size < self._total:
            self._offset += self._page_size
            self.reload()

    @on(Button.Pressed, "#table-edit")
    def _edit_table(self) -> None:
        _ = self.post_message(self.EditTableRequested(self.table_name))

    @on(Button.Pressed, "#table-delete")
    def _delete_table(self) -> None:
        _ = self.post_message(self.DeleteTableRequested(self.table_name))

    @on(Button.Pressed, "#row-edit")
    def _edit_row(self) -> None:
        self.edit_selected_row()

    @on(Button.Pressed, "#row-delete")
    def _delete_row(self) -> None:
        self.delete_selected_rows()

    def delete_selected_rows(self) -> None:
        rowids = self._selected_or_cursor_rowids()
        if not rowids:
            return
        if len(rowids) == 1:
            message = "Delete this row? This cannot be undone."
        else:
            message = f"Delete {len(rowids):,} selected rows? This cannot be undone."
        _ = self._catalog_app().push_screen(
            ConfirmModal(
                "Delete row" if len(rowids) == 1 else "Delete rows",
                message,
                confirm_label="Delete",
                destructive=True,
            ),
            lambda confirmed: self._delete_rows(rowids, confirmed),
        )

    def _delete_rows(self, rowids: list[int], confirmed: bool | None) -> None:
        if not confirmed:
            return
        deleted = 0
        for rowid in rowids:
            try:
                self.storage.delete_row(self.table_name, rowid)
            except Exception as e:
                self.notify(f"Could not delete row: {e}", severity="error")
                continue
            deleted += 1
        if deleted:
            _ = self.post_message(self.TableChanged(self.table_name))
            self.reload()
            self.notify(
                f"Deleted {deleted:,} {'row' if deleted == 1 else 'rows'}",
                severity="information",
            )

    @on(Button.Pressed, "#table-export")
    def _export_table(self) -> None:
        _ = self.post_message(self.ExportTableRequested(self.table_name))

    @on(Button.Pressed, "#row-export")
    def _export_row(self) -> None:
        rowids = self._selected_or_cursor_rowids()
        if not rowids:
            return
        safe_name = storage.sanitize_identifier(self.table_name) or "table"
        default_path = Path.cwd() / f"{safe_name}-selection.csv"
        _ = self._catalog_app().push_screen(
            ExportSelectionModal(
                title=f"Export {len(rowids):,} {'row' if len(rowids) == 1 else 'rows'}",
                hint="Choose the output CSV file.",
                default_path=default_path,
                placeholder="~/selection.csv",
            ),
            lambda path: self._export_selected_rows(rowids, path),
        )

    def _export_selected_rows(self, rowids: list[int], path: Path | None) -> None:
        if path is None:
            return
        table = self.storage.get_table(self.table_name)
        if table is None:
            self.notify("Table no longer exists", severity="error")
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            count = 0
            with path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(table.columns)
                for rowid in rowids:
                    row = self.storage.get_row(self.table_name, rowid)
                    if row is None:
                        continue
                    writer.writerow(
                        [_cell_text(row.get(column)) for column in table.columns]
                    )
                    count += 1
        except Exception as e:
            self.notify(f"Could not export rows: {e}", severity="error")
            return
        self.notify(
            f"Exported {count:,} {'row' if count == 1 else 'rows'} to {path}",
            severity="information",
        )

    def _selected_rowids(self) -> list[int]:
        rowids: list[int] = []
        for key in self._rows_widget().selected_keys:
            try:
                rowids.append(int(key))
            except ValueError:
                continue
        return sorted(rowids)

    def _cursor_rowid(self) -> int | None:
        table = self._rows_widget()
        if table.row_count == 0:
            return None
        row_index = min(table.cursor_coordinate.row, table.row_count - 1)
        key = table.ordered_rows[row_index].key.value
        if not isinstance(key, str):
            return None
        try:
            return int(key)
        except ValueError:
            return None

    def _selected_or_cursor_rowids(self) -> list[int]:
        selected = self._selected_rowids()
        if selected:
            return selected
        cursor_rowid = self._cursor_rowid()
        return [] if cursor_rowid is None else [cursor_rowid]

    def _selected_or_cursor_rowid(self) -> int | None:
        rowids = self._selected_or_cursor_rowids()
        return rowids[0] if len(rowids) == 1 else None


def _cell_text(value: SqlValue) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _preview(value: SqlValue) -> str:
    text = _cell_text(value).replace("\n", " ").replace("\r", " ")
    return text
