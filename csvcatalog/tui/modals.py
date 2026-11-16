import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast, final, override

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import (
    Container,
    Horizontal,
    HorizontalScroll,
    Vertical,
    VerticalScroll,
)
from textual.screen import ModalScreen
from textual.suggester import SuggestFromList
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    SelectionList,
    Static,
    TextArea,
)
from textual.widgets.selection_list import Selection

from ..config import Settings
from ..storage import Table
from .format import merge_date
from .widgets import PathField


def _scroll_modal_home(widget: Widget) -> None:
    _ = widget.query_one(".modal").scroll_home(animate=False)


@dataclass(frozen=True)
class ColumnsPatch:
    """pending column renames and deletions"""

    renames: dict[str, str]
    deletions: list[str]


@dataclass(frozen=True)
class TablePatch:
    """validated changes produced by the table editor"""

    name: str
    description: str
    created_at: str
    columns: ColumnsPatch


@dataclass(frozen=True)
class RowPatch:
    """validated changes produced by the row editor"""

    values: dict[str, str]
    delete: bool = False


@dataclass(frozen=True)
class RowSearchResult:
    """search or replace request produced by the row search dialog"""

    query: str
    columns: list[str]
    replace: bool = False
    replacement: str = ""


@dataclass(frozen=True)
class PageRequest:
    """pagination changes produced by the rows dialog"""

    limit: int
    page: int
    row: int | None = None


@final
class ConfirmModal(ModalScreen[bool]):
    """small reusable confirmation dialog"""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(
        self,
        title: str,
        message: str,
        *,
        confirm_label: str = "Confirm",
        destructive: bool = False,
    ) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._confirm_label = confirm_label
        self._destructive = destructive

    @override
    def compose(self) -> ComposeResult:
        with Container(classes="modal narrow"):
            yield Static(self._title, classes="modal-title")
            yield Static(self._message, classes="modal-message")
            with HorizontalScroll(classes="modal-actions"):
                yield Button("Cancel", id="confirm-cancel")
                yield Button(
                    self._confirm_label,
                    id="confirm-ok",
                    variant="error" if self._destructive else "primary",
                )

    def on_mount(self) -> None:
        if self._destructive:
            _ = self.query_one("#confirm-cancel", Button).focus()
        else:
            _ = self.query_one("#confirm-ok", Button).focus()

    @on(Button.Pressed, "#confirm-cancel")
    def _cancel(self) -> None:
        _ = self.dismiss(False)

    @on(Button.Pressed, "#confirm-ok")
    def _confirm(self) -> None:
        _ = self.dismiss(True)

    def action_cancel(self) -> None:
        _ = self.dismiss(False)


@final
class DatabasePickerModal(ModalScreen[Path | None]):
    """ask for a database path when the configured one cannot be opened"""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(
        self,
        current_path: Path | None,
        *,
        error: str | None = None,
        missing: bool = False,
    ) -> None:
        super().__init__()
        self._current_path = current_path
        self._error = error
        self._missing = missing

    @override
    def compose(self) -> ComposeResult:
        title = "Database not found" if self._missing else "Could not open database"
        with Container(classes="modal"):
            yield Static(title, classes="modal-title")
            if self._missing:
                yield Static(
                    "Choose an existing database or enter a new path to create one.",
                    classes="modal-hint",
                )
            else:
                yield Static(
                    "The configured database could not be opened. Choose another file.",
                    classes="modal-hint",
                )
            if self._error:
                yield Static(
                    Text(self._error, style="#fca5a5"),
                    classes="modal-error",
                )
            yield Label("Database path", classes="form-label")
            yield PathField(
                str(self._current_path) if self._current_path else "",
                placeholder="~/catalog.db",
                id="database-path",
            )
            yield Static(
                "Type a path · ↓ suggestions · Enter to open",
                classes="form-note",
            )
            with HorizontalScroll(classes="modal-actions"):
                yield Button("Quit", id="database-cancel")
                yield Button(
                    "Open / create",
                    id="database-open",
                    variant="primary",
                )

    def on_mount(self) -> None:
        _ = self.call_after_refresh(lambda: _scroll_modal_home(self))

    @on(Button.Pressed, "#database-cancel")
    def _cancel(self) -> None:
        _ = self.dismiss(None)

    @on(Button.Pressed, "#database-open")
    def _open(self) -> None:
        self._submit()

    @on(Input.Submitted, "#path-input")
    def _submit(self) -> None:
        raw_path = self.query_one("#database-path", PathField).value.strip()
        if not raw_path:
            self.notify("Database path cannot be empty", severity="error")
            return
        path = Path(raw_path).expanduser().resolve()
        if path.is_dir():
            self.notify("That path is a directory, choose a file", severity="error")
            return
        _ = self.dismiss(path)

    def action_cancel(self) -> None:
        _ = self.dismiss(None)


@final
class SettingsModal(ModalScreen[Settings | None]):
    """edit application settings without leaving the catalog"""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

    @override
    def compose(self) -> ComposeResult:
        with Container(classes="modal"):
            yield Static("Settings", classes="modal-title")
            yield Static(
                "Changes are saved to your local config.",
                classes="modal-hint",
            )
            with Vertical(classes="form"):
                yield Label("Database path", classes="form-label")
                yield PathField(
                    str(self._settings.db_path or ""),
                    placeholder="default catalog.db",
                    id="db-path",
                )
                with Horizontal(classes="form-row compact"):
                    yield Label("Encryption", classes="form-label")
                    yield Static(
                        Text(
                            "Enabled" if self._settings.encryption else "Disabled",
                            style="#34d399" if self._settings.encryption else "#94a3b8",
                        ),
                        classes="form-value",
                    )
                yield Static(
                    "Encryption is managed from the CLI.",
                    classes="form-note",
                )
            with HorizontalScroll(classes="modal-actions"):
                yield Button("Cancel", id="settings-cancel")
                yield Button("Save", id="settings-save", variant="primary")

    def on_mount(self) -> None:
        _ = self.call_after_refresh(lambda: _scroll_modal_home(self))

    @on(Button.Pressed, "#settings-cancel")
    def _cancel(self) -> None:
        _ = self.dismiss(None)

    @on(Input.Submitted, "#path-input")
    def _submitted(self) -> None:
        self._save()

    @on(Button.Pressed, "#settings-save")
    def _save(self) -> None:
        raw_path = self.query_one("#db-path", PathField).value.strip()
        db_path = Path(raw_path).expanduser() if raw_path else None
        _ = self.dismiss(
            Settings(
                db_path=db_path,
                encryption=self._settings.encryption,
                filters=dict(self._settings.filters),
            )
        )

    def action_cancel(self) -> None:
        _ = self.dismiss(None)

    def action_save(self) -> None:
        self._save()


@final
class FiltersModal(ModalScreen[dict[str, str] | None]):
    """view, add, update and remove saved regex filters"""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def __init__(self, filters: dict[str, str]) -> None:
        super().__init__()
        self._filters = dict(filters)
        self._initial = dict(filters)

    @override
    def compose(self) -> ComposeResult:
        with Container(classes="modal wide filters-modal"):
            yield Static("Saved filters", classes="modal-title")
            yield Static(
                "Select a filter to edit, or enter a new name and pattern.",
                classes="modal-hint",
            )
            with VerticalScroll(classes="modal-body"):
                yield DataTable(
                    id="filter-table", cursor_type="row", zebra_stripes=True
                )
                with Vertical(classes="form"):
                    with Horizontal(classes="form-row"):
                        yield Label("Name", classes="form-label")
                        yield Input(
                            placeholder="Filter name",
                            suggester=SuggestFromList(
                                self._filters.keys(), case_sensitive=False
                            ),
                            id="filter-name",
                        )
                    with Horizontal(classes="form-row"):
                        yield Label("Regex", classes="form-label")
                        yield Input(
                            placeholder="Regular expression", id="filter-pattern"
                        )
                yield Static("", id="filter-count", classes="modal-hint")
            with HorizontalScroll(classes="modal-actions"):
                yield Button("Cancel", id="filters-cancel")
                yield Button("Remove", id="filters-delete", variant="error")
                yield Button("Add", id="filters-upsert")
                yield Button("Save", id="filters-save", variant="primary")

    def on_mount(self) -> None:
        table = self._filters_widget()
        _ = table.add_column("Name", key="name", width=24)
        _ = table.add_column("Regex", key="pattern")
        self._render_filters()
        if self._filters:
            _ = table.focus()
        else:
            _ = self.query_one("#filter-name", Input).focus()
        _ = self.call_after_refresh(lambda: _scroll_modal_home(self))

    def _filters_widget(self) -> DataTable[Text]:
        return cast(DataTable[Text], self.query_one("#filter-table", DataTable))

    def _render_filters(self) -> None:
        table = self._filters_widget()
        _ = table.clear(columns=False)
        for name in sorted(self._filters):
            _ = table.add_row(
                Text(name),
                Text(self._filters[name]),
                key=name,
            )
        count = self.query_one("#filter-count", Static)
        filter_count = len(self._filters)
        if filter_count == 0:
            count.update("No saved filters")
        else:
            count.update(
                f"{filter_count:,} saved {'filter' if filter_count == 1 else 'filters'}"
            )

    @on(DataTable.RowHighlighted, "#filter-table")
    def _load_filter(self, event: DataTable.RowHighlighted) -> None:
        name = event.row_key.value
        if name is None:
            return
        self.query_one("#filter-name", Input).value = name
        self.query_one("#filter-pattern", Input).value = self._filters.get(name, "")

    @on(Input.Changed, "#filter-name")
    def _update_upsert_label(self, event: Input.Changed) -> None:
        self.query_one("#filters-upsert", Button).label = (
            "Update" if event.value.strip() in self._filters else "Add"
        )

    @on(Button.Pressed, "#filters-upsert")
    def _upsert_filter(self) -> None:
        name = self.query_one("#filter-name", Input).value.strip()
        pattern = self.query_one("#filter-pattern", Input).value
        if not name:
            self.notify("Filter name cannot be empty", severity="error")
            return
        if not pattern:
            self.notify("Regex pattern cannot be empty", severity="error")
            return
        try:
            _ = re.compile(pattern)
        except re.error as e:
            self.notify(f"Invalid regex: {e}", severity="error")
            return
        existed = name in self._filters
        self._filters[name] = pattern
        self._render_filters()
        action = "updated" if existed else "added"
        self.notify(
            f"Filter {action} — press Save to apply",
            severity="information",
        )

    @on(Button.Pressed, "#filters-delete")
    def _delete_filter(self) -> None:
        name = self.query_one("#filter-name", Input).value.strip()
        if name not in self._filters:
            self.notify("Select a saved filter to remove", severity="warning")
            return
        del self._filters[name]
        self.query_one("#filter-name", Input).value = ""
        self.query_one("#filter-pattern", Input).value = ""
        self._render_filters()
        self.notify(f"Filter '{name}' removed", severity="information")

    @on(Button.Pressed, "#filters-cancel")
    def _cancel(self) -> None:
        _ = self.dismiss(None)

    @on(Button.Pressed, "#filters-save")
    def _save(self) -> None:
        _ = self.dismiss(self._filters if self._filters != self._initial else None)

    def action_cancel(self) -> None:
        _ = self.dismiss(None)

    def action_save(self) -> None:
        self._save()


@final
class ColumnEditor(Vertical):
    """inline editor for renaming and deleting table columns"""

    def __init__(self, columns: list[str]) -> None:
        super().__init__(classes="column-editor")
        self._original = list(columns)
        self._current = {column: column for column in columns}
        self._deleted: set[str] = set()
        self._selected: str | None = None
        self._pending = False

    @override
    def compose(self) -> ComposeResult:
        yield DataTable(id="column-table", cursor_type="row", zebra_stripes=True)
        yield Label("Column name", classes="form-label")
        yield Input(
            placeholder="New column name",
            id="column-name",
            classes="column-name-input",
        )
        with Horizontal(classes="modal-actions inline"):
            yield Button("Rename", id="column-rename")
            yield Button("Delete", id="column-delete", variant="error")

    def on_mount(self) -> None:
        table = self._column_table()
        _ = table.add_column("Column", key="name")
        self._render_columns()

    def _column_table(self) -> DataTable[Text]:
        return cast(DataTable[Text], self.query_one("#column-table", DataTable))

    def _active_columns(self) -> list[str]:
        return [column for column in self._original if column not in self._deleted]

    def _render_columns(self) -> None:
        table = self._column_table()
        _ = table.clear(columns=False)
        for original in self._active_columns():
            _ = table.add_row(
                Text(self._current[original], style="#f5f5f7"),
                key=original,
            )
        if self._selected in self._deleted:
            self._selected = None
            self.query_one("#column-name", Input).value = ""

    @on(DataTable.RowHighlighted, "#column-table")
    def _load_column(self, event: DataTable.RowHighlighted) -> None:
        original = event.row_key.value
        if not isinstance(original, str) or original in self._deleted:
            return
        self._selected = original
        self.query_one("#column-name", Input).value = self._current[original]

    @on(Button.Pressed, "#column-rename")
    def _rename_column(self) -> None:
        if self._selected is None:
            self.notify("Select a column first", severity="warning")
            return
        new_name = self.query_one("#column-name", Input).value.strip()
        if not new_name:
            self.notify("Column name cannot be empty", severity="error")
            return
        used = {
            self._current[column]
            for column in self._active_columns()
            if column != self._selected
        }
        if new_name in used:
            self.notify(f"Column '{new_name}' already exists", severity="error")
            return
        self._current[self._selected] = new_name
        self._pending = True
        self._render_columns()
        self.notify(f"Column will be renamed to '{new_name}'", severity="information")

    @on(Button.Pressed, "#column-delete")
    def _delete_column(self) -> None:
        if self._selected is None:
            self.notify("Select a column first", severity="warning")
            return
        if len(self._active_columns()) <= 1:
            self.notify("A table must keep at least one column", severity="error")
            return
        deleted = self._selected
        self._deleted.add(deleted)
        self._selected = None
        self._pending = True
        self._render_columns()
        self.notify(f"Column '{deleted}' will be deleted", severity="warning")

    def patch(self) -> ColumnsPatch:
        renames = {
            original: current
            for original, current in self._current.items()
            if original != current
        }
        return ColumnsPatch(renames=renames, deletions=sorted(self._deleted))

    @property
    def changed(self) -> bool:
        return self._pending


@final
class ColumnsModal(ModalScreen[ColumnsPatch | None]):
    """edit columns from the table viewer"""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def __init__(self, columns: list[str]) -> None:
        super().__init__()
        self._columns = list(columns)

    @override
    def compose(self) -> ComposeResult:
        with Container(classes="modal wide columns-modal"):
            yield Static("Edit columns", classes="modal-title")
            yield Static(
                "Select a column, then rename or delete it.",
                classes="modal-hint",
            )
            with VerticalScroll(classes="modal-body"):
                yield ColumnEditor(self._columns)
            with HorizontalScroll(classes="modal-actions"):
                yield Button("Cancel", id="columns-cancel")
                yield Button("Save", id="columns-save", variant="primary")

    def on_mount(self) -> None:
        table = cast(
            DataTable[Text],
            self.query_one(ColumnEditor).query_one("#column-table", DataTable),
        )
        _ = table.focus()

    @on(Button.Pressed, "#columns-cancel")
    def _cancel(self) -> None:
        _ = self.dismiss(None)

    @on(Button.Pressed, "#columns-save")
    def _save(self) -> None:
        _ = self.dismiss(self.query_one(ColumnEditor).patch())

    def action_cancel(self) -> None:
        _ = self.dismiss(None)

    def action_save(self) -> None:
        self._save()


@final
class SearchRowsModal(ModalScreen[str | None]):
    """compact search prompt that keeps the data view unobstructed"""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "submit", "Search", show=False),
    ]

    def __init__(
        self,
        current: str,
        *,
        title: str = "Search rows",
        hint: str = "Search across all columns in this table.",
        placeholder: str = "Search text…",
    ) -> None:
        super().__init__()
        self._current = current
        self._title = title
        self._hint = hint
        self._placeholder = placeholder

    @override
    def compose(self) -> ComposeResult:
        with Container(classes="modal narrow"):
            yield Static(self._title, classes="modal-title")
            yield Static(self._hint, classes="modal-hint")
            yield Input(
                value=self._current,
                placeholder=self._placeholder,
                id="search-input",
            )
            with HorizontalScroll(classes="modal-actions"):
                yield Button("Clear", id="search-clear")
                yield Button("Cancel", id="search-cancel")
                yield Button("Search", id="search-apply", variant="primary")

    def on_mount(self) -> None:
        search = self.query_one("#search-input", Input)
        _ = search.focus()
        search.select_all()

    @on(Input.Submitted, "#search-input")
    def _submitted(self) -> None:
        self._submit()

    @on(Button.Pressed, "#search-clear")
    def _clear(self) -> None:
        _ = self.dismiss("")

    @on(Button.Pressed, "#search-cancel")
    def _cancel(self) -> None:
        _ = self.dismiss(None)

    @on(Button.Pressed, "#search-apply")
    def _apply(self) -> None:
        self._submit()

    def _submit(self) -> None:
        _ = self.dismiss(self.query_one("#search-input", Input).value.strip())

    def action_cancel(self) -> None:
        _ = self.dismiss(None)

    def action_submit(self) -> None:
        self._submit()


@final
class RowSearchModal(ModalScreen[RowSearchResult | None]):
    """search and replace across selected columns"""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "submit", "Search", show=False),
    ]

    def __init__(
        self,
        columns: list[str],
        current_query: str,
        current_columns: list[str] | None,
    ) -> None:
        super().__init__()
        self._columns = columns
        self._current_query = current_query
        self._current_columns = current_columns

    @override
    def compose(self) -> ComposeResult:
        current = set(self._current_columns or self._columns)
        with Container(classes="modal search-modal"):
            yield Static("Search rows", classes="modal-title")
            yield Static(
                "Search across selected columns, or replace every match.",
                classes="modal-hint",
            )
            yield Label("Search in", classes="form-label")
            yield SelectionList(
                *[
                    Selection(column, column, initial_state=column in current)
                    for column in self._columns
                ],
                id="search-columns",
                compact=True,
            )
            yield Label("Find", classes="form-label")
            yield Input(
                value=self._current_query,
                placeholder="Search text…",
                id="search-input",
            )
            yield Label("Replace with", classes="form-label")
            yield Input(
                placeholder="Replacement text (optional)",
                id="replace-input",
            )
            with HorizontalScroll(classes="modal-actions"):
                yield Button("Clear", id="search-clear")
                yield Button("Cancel", id="search-cancel")
                yield Button("Replace all", id="search-replace")
                yield Button("Search", id="search-apply", variant="primary")

    def on_mount(self) -> None:
        search = self.query_one("#search-input", Input)
        _ = search.focus()
        search.select_all()

    def _selected_columns(self) -> list[str]:
        selection_list = cast(
            SelectionList[str],
            self.query_one("#search-columns", SelectionList),
        )
        return list(selection_list.selected)

    def _result(self, *, replace: bool) -> RowSearchResult | None:
        query = self.query_one("#search-input", Input).value
        if not query:
            self.notify("Search text cannot be empty", severity="error")
            return None
        columns = self._selected_columns()
        if not columns:
            self.notify("Select at least one column", severity="error")
            return None
        return RowSearchResult(
            query=query,
            columns=columns,
            replace=replace,
            replacement=self.query_one("#replace-input", Input).value,
        )

    @on(Input.Submitted, "#search-input")
    def _submitted(self) -> None:
        self._search()

    @on(Button.Pressed, "#search-clear")
    def _clear(self) -> None:
        _ = self.dismiss(
            RowSearchResult(
                query="",
                columns=self._selected_columns(),
            )
        )

    @on(Button.Pressed, "#search-cancel")
    def _cancel(self) -> None:
        _ = self.dismiss(None)

    @on(Button.Pressed, "#search-apply")
    def _search(self) -> None:
        result = self._result(replace=False)
        if result is not None:
            _ = self.dismiss(result)

    @on(Button.Pressed, "#search-replace")
    def _replace(self) -> None:
        result = self._result(replace=True)
        if result is not None:
            _ = self.dismiss(result)

    def action_cancel(self) -> None:
        _ = self.dismiss(None)

    def action_submit(self) -> None:
        self._search()


@final
class PaginationModal(ModalScreen[PageRequest | None]):
    """change page size or jump to a page / record"""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "apply", "Apply", show=False),
    ]

    def __init__(self, total: int, page_size: int, current_page: int) -> None:
        super().__init__()
        self._total = total
        self._page_size = page_size
        self._current_page = current_page

    @override
    def compose(self) -> ComposeResult:
        pages = max(1, (self._total + self._page_size - 1) // self._page_size)
        with Container(classes="modal narrow pagination-modal"):
            yield Static("Rows", classes="modal-title")
            yield Static(
                f"{self._total:,} rows · page {self._current_page:,} of {pages:,}",
                classes="modal-hint",
            )
            yield Label("Rows per page", classes="form-label")
            yield Input(
                value=str(self._page_size),
                type="integer",
                id="page-size",
            )
            yield Label("Go to page", classes="form-label")
            yield Input(
                value=str(self._current_page),
                type="integer",
                id="page-number",
            )
            yield Label("Go to row", classes="form-label")
            yield Input(
                placeholder="Row number (optional)",
                type="integer",
                id="row-number",
            )
            yield Static(
                "If a row is set, it takes priority over the page number.",
                classes="form-note",
            )
            with HorizontalScroll(classes="modal-actions"):
                yield Button("Cancel", id="pagination-cancel")
                yield Button("Apply", id="pagination-apply", variant="primary")

    def on_mount(self) -> None:
        size = self.query_one("#page-size", Input)
        _ = size.focus()
        size.select_all()

    def _parse_int(self, selector: str) -> int | None:
        raw = self.query_one(selector, Input).value.strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    @on(Input.Submitted)
    def _submitted(self) -> None:
        self._apply()

    @on(Button.Pressed, "#pagination-cancel")
    def _cancel(self) -> None:
        _ = self.dismiss(None)

    @on(Button.Pressed, "#pagination-apply")
    def _apply(self) -> None:
        limit = self._parse_int("#page-size")
        if limit is None or limit < 1:
            self.notify("Rows per page must be a positive number", severity="error")
            return
        limit = min(limit, 5000)
        row = self._parse_int("#row-number")
        if row is not None and row < 1:
            self.notify("Row number must be positive", severity="error")
            return
        page = self._parse_int("#page-number")
        if page is None or page < 1:
            if row is None:
                self.notify("Page number must be positive", severity="error")
                return
            page = 1
        _ = self.dismiss(PageRequest(limit=limit, page=page, row=row))

    def action_cancel(self) -> None:
        _ = self.dismiss(None)

    def action_apply(self) -> None:
        self._apply()


@final
class ExportTableModal(ModalScreen[Path | None]):
    """choose where to export a table as csv"""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "export", "Export", show=False),
    ]

    def __init__(self, table_name: str, default_path: Path) -> None:
        super().__init__()
        self._table_name = table_name
        self._default_path = default_path

    @override
    def compose(self) -> ComposeResult:
        with Container(classes="modal narrow"):
            yield Static(f"Export · {self._table_name}", classes="modal-title")
            yield Static("Choose the output CSV file.", classes="modal-hint")
            yield PathField(
                str(self._default_path),
                placeholder="~/table.csv",
                suffixes=frozenset({".csv"}),
                id="export-path",
            )
            yield Static(
                "Type a path or use ↓ for suggestions",
                classes="form-note",
            )
            with HorizontalScroll(classes="modal-actions"):
                yield Button("Cancel", id="export-cancel")
                yield Button("Export", id="export-save", variant="primary")

    def on_mount(self) -> None:
        _ = self.call_after_refresh(lambda: _scroll_modal_home(self))

    @on(Input.Submitted, "#path-input")
    def _submitted(self) -> None:
        self._export()

    @on(Button.Pressed, "#export-cancel")
    def _cancel(self) -> None:
        _ = self.dismiss(None)

    @on(Button.Pressed, "#export-save")
    def _export(self) -> None:
        raw = self.query_one("#export-path", PathField).value.strip()
        if not raw:
            self.notify("Export path cannot be empty", severity="error")
            return
        path = Path(raw).expanduser()
        if path.is_dir():
            self.notify("Choose a file path, not a directory", severity="error")
            return
        if path.suffix.casefold() != ".csv":
            path = path.with_suffix(".csv")
        _ = self.dismiss(path)

    def action_cancel(self) -> None:
        _ = self.dismiss(None)

    def action_export(self) -> None:
        self._export()


@final
class ExportSelectionModal(ModalScreen[Path | None]):
    """choose a destination for a multi-item export"""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "export", "Export", show=False),
    ]

    def __init__(
        self,
        *,
        title: str,
        hint: str,
        default_path: Path,
        directory: bool = False,
        placeholder: str = "",
        button_label: str = "Export",
    ) -> None:
        super().__init__()
        self._title = title
        self._hint = hint
        self._default_path = default_path
        self._directory = directory
        self._placeholder = placeholder
        self._button_label = button_label

    @override
    def compose(self) -> ComposeResult:
        with Container(classes="modal narrow"):
            yield Static(self._title, classes="modal-title")
            yield Static(self._hint, classes="modal-hint")
            yield PathField(
                str(self._default_path),
                placeholder=self._placeholder,
                suffixes=frozenset() if self._directory else frozenset({".csv"}),
                id="export-selection-path",
            )
            yield Static(
                "Type a path or use ↓ for suggestions",
                classes="form-note",
            )
            with HorizontalScroll(classes="modal-actions"):
                yield Button("Cancel", id="export-selection-cancel")
                yield Button(
                    self._button_label,
                    id="export-selection-save",
                    variant="primary",
                )

    def on_mount(self) -> None:
        _ = self.call_after_refresh(lambda: _scroll_modal_home(self))

    @on(Input.Submitted, "#path-input")
    def _submitted(self) -> None:
        self._export()

    @on(Button.Pressed, "#export-selection-cancel")
    def _cancel(self) -> None:
        _ = self.dismiss(None)

    @on(Button.Pressed, "#export-selection-save")
    def _export(self) -> None:
        raw = self.query_one("#export-selection-path", PathField).value.strip()
        if not raw:
            self.notify("Export path cannot be empty", severity="error")
            return
        path = Path(raw).expanduser()
        if self._directory:
            if path.exists() and not path.is_dir():
                self.notify("Choose a folder, not a file", severity="error")
                return
        else:
            if path.is_dir():
                self.notify("Choose a file path, not a directory", severity="error")
                return
            if path.suffix.casefold() != ".csv":
                path = path.with_suffix(".csv")
        _ = self.dismiss(path)

    def action_cancel(self) -> None:
        _ = self.dismiss(None)

    def action_export(self) -> None:
        self._export()


@final
class RowEditModal(ModalScreen[RowPatch | None]):
    """edit all cells of a row at once"""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def __init__(
        self,
        table_name: str,
        columns: list[str],
        values: dict[str, str],
        *,
        rowid: int | None = None,
    ) -> None:
        super().__init__()
        self._table_name = table_name
        self._columns = columns
        self._values = values
        self._rowid = rowid

    @override
    def compose(self) -> ComposeResult:
        title = "New row" if self._rowid is None else "Edit row"
        with Container(classes="modal row-modal"):
            yield Static(f"{title} · {self._table_name}", classes="modal-title")
            with VerticalScroll(classes="modal-body"):
                for index, column in enumerate(self._columns):
                    yield Label(column, classes="form-label")
                    yield TextArea(
                        self._values.get(column, ""),
                        id=f"cell-{index}",
                        classes="cell-editor",
                    )
            with HorizontalScroll(classes="modal-actions"):
                yield Button("Cancel", id="row-cancel")
                if self._rowid is not None:
                    yield Button("Delete", id="row-delete", variant="error")
                yield Button("Save", id="row-save", variant="primary")

    def on_mount(self) -> None:
        if self._columns:
            _ = self.query_one("#cell-0", TextArea).focus()

    @on(Button.Pressed, "#row-cancel")
    def _cancel(self) -> None:
        _ = self.dismiss(None)

    @on(Button.Pressed, "#row-delete")
    def _delete(self) -> None:
        _ = self.dismiss(RowPatch(values={}, delete=True))

    @on(Button.Pressed, "#row-save")
    def _save(self) -> None:
        values = {
            column: self.query_one(f"#cell-{index}", TextArea).text
            for index, column in enumerate(self._columns)
        }
        _ = self.dismiss(RowPatch(values=values))

    def action_cancel(self) -> None:
        _ = self.dismiss(None)

    def action_save(self) -> None:
        self._save()


@final
class EditTableModal(ModalScreen[TablePatch | None]):
    """edit the displayed metadata of a table"""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def __init__(self, table: Table) -> None:
        super().__init__()
        self._table = table
        self._columns_patch = ColumnsPatch(renames={}, deletions=[])

    @override
    def compose(self) -> ComposeResult:
        with Container(classes="modal edit-table-modal"):
            yield Static(f"Edit table · {self._table.name}", classes="modal-title")
            with VerticalScroll(classes="modal-body"):
                yield Label("Table name", classes="form-label")
                yield Input(value=self._table.name, id="table-name")
                yield Label("Description", classes="form-label")
                yield Input(
                    value=self._table.description or "",
                    id="table-description",
                )
                yield Label("Date (yyyy-mm-dd)", classes="form-label")
                yield Input(
                    value=self._table.created_at.split("T")[0],
                    placeholder="yyyy-mm-dd",
                    id="table-date",
                )
                with Horizontal(classes="form-row compact", id="columns-row"):
                    yield Label("Columns", classes="form-label")
                    yield Static(
                        f"{len(self._table.columns)} columns",
                        classes="form-value",
                        id="columns-count",
                    )
                    yield Button(
                        "Edit columns",
                        id="edit-columns",
                        classes="compact-action accent",
                        tooltip="Rename or delete table columns",
                    )
                yield Static(
                    f"{self._table.count:,} rows",
                    classes="form-note",
                )
                yield Static("", id="columns-status", classes="form-note")
            with HorizontalScroll(classes="modal-actions"):
                yield Button("Cancel", id="edit-cancel")
                yield Button("Save", id="edit-save", variant="primary")

    def on_mount(self) -> None:
        _ = self.call_after_refresh(lambda: _scroll_modal_home(self))
        _ = self.query_one("#table-name", Input).focus()

    @on(Button.Pressed, "#edit-columns")
    def _open_columns(self) -> None:
        _ = cast(App[None], self.app).push_screen(
            ColumnsModal(self._table.columns),
            self._apply_columns_patch,
        )

    def _apply_columns_patch(self, patch: ColumnsPatch | None) -> None:
        if patch is None:
            return
        self._columns_patch = patch
        changes = len(patch.renames) + len(patch.deletions)
        status = self.query_one("#columns-status", Static)
        if changes:
            status.update(
                f"{changes} column {'change' if changes == 1 else 'changes'} pending"
            )
        else:
            status.update("")

    @on(Button.Pressed, "#edit-cancel")
    def _cancel(self) -> None:
        _ = self.dismiss(None)

    @on(Button.Pressed, "#edit-save")
    def _save(self) -> None:
        name = self.query_one("#table-name", Input).value.strip()
        if not name:
            self.notify("Table name cannot be empty", severity="error")
            return
        date_str = self.query_one("#table-date", Input).value.strip()
        try:
            created_at = merge_date(self._table.created_at, date_str)
        except ValueError:
            self.notify("Invalid date, expected yyyy-mm-dd", severity="error")
            return
        _ = self.dismiss(
            TablePatch(
                name=name,
                description=self.query_one("#table-description", Input).value,
                created_at=created_at,
                columns=self._columns_patch,
            )
        )

    def action_cancel(self) -> None:
        _ = self.dismiss(None)

    def action_save(self) -> None:
        self._save()
