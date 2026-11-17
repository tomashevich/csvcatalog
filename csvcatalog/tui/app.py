import time
from collections.abc import Callable
from pathlib import Path
from typing import final, override

from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, ContentSwitcher, DataTable, Footer, Static

from .. import config, storage
from ..config import Settings
from ..storage import BaseStorage
from ..storage import Table as CatalogTable
from .format import database_size, human_size, truncate
from .import_wizard import CsvImportWizard, ImportResult
from .modals import (
    ColumnsPatch,
    DatabasePickerModal,
    DeleteTableModal,
    EditTableModal,
    ExportSelectionModal,
    ExportTableModal,
    FiltersModal,
    SearchRowsModal,
    SettingsModal,
    TablePatch,
)
from .selection import MultiSelectTable
from .table_view import TableEditorView
from .tabs import EditorTab, EditorTabs

HEADER_SORT_KEYS = {
    "name": "name",
    "description": "description",
    "rows": "rows",
    "columns": "columns",
    "created": "date",
}

HEADER_LABELS = {
    "name": "Name",
    "description": "Description",
    "rows": "Rows",
    "columns": "Columns",
    "created": "Created",
}


@final
class CatalogTUI(App[None]):
    """interactive terminal browser for a csv catalog"""

    CSS_PATH = "app.tcss"
    TITLE = "csvcatalog"
    SUB_TITLE = "interactive catalog browser"

    BINDINGS = [
        Binding("ctrl+c", "request_quit", "Quit ×2", priority=True),
        Binding("ctrl+q", "quit_hint", "Quit", show=False, priority=True),
        Binding("/,.,ctrl+f", "focus_search", "Search", key_display="/"),
        Binding("r,к,ctrl+r", "refresh_data", "Refresh", key_display="r"),
        Binding("s,ы", "open_settings", "Settings", key_display="s"),
        Binding("f,а", "open_filters", "Filters", key_display="f"),
        Binding("i,ш", "import_csv", "Import", key_display="i", show=False),
        Binding(
            "e,у,ctrl+e",
            "edit_table",
            "Edit",
            key_display="e",
            show=False,
        ),
        Binding(
            "d,в",
            "delete_table",
            "Delete",
            key_display="d",
            show=False,
        ),
        Binding("ctrl+w", "close_tab", "Close tab", show=False),
        Binding("escape", "clear_search", "Clear", show=False),
    ]

    def __init__(
        self,
        storage_instance: BaseStorage | None,
        settings: Settings,
        db_path: Path,
        *,
        db_error: str | None = None,
        on_storage_change: Callable[[BaseStorage | None], None] | None = None,
    ) -> None:
        super().__init__()
        self.storage: BaseStorage | None = storage_instance
        self.settings = settings
        self.db_path = db_path
        self._db_error = db_error
        self._on_storage_change = on_storage_change
        self._tables: list[CatalogTable] = []
        self._by_name: dict[str, CatalogTable] = {}
        self._selected_name: str | None = None
        self._query: str = ""
        self._sort_key: str = "name"
        self._sort_desc: bool = False
        self._last_interrupt: float | None = None
        self._tab_ids: dict[str, str] = {}
        self._views: dict[str, TableEditorView] = {}
        self._tab_counter = 0

    @override
    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static("csvcatalog", id="brand")
            yield Static(str(self.db_path), id="path-label")
        with Container(id="body"):
            yield EditorTabs(id="tab-bar")
            with ContentSwitcher(initial="overview", id="content-switcher"):
                with Vertical(id="overview"):
                    with Horizontal(id="overview-toolbar"):
                        yield Button(
                            "Search",
                            id="overview-search",
                            classes="compact-action",
                            tooltip="Search tables by name, description or column",
                        )
                        yield Button(
                            "Filters",
                            id="overview-filters",
                            classes="compact-action",
                            tooltip="Manage saved regex filters",
                        )
                        yield Button(
                            "Import",
                            id="overview-import",
                            classes="compact-action accent",
                            tooltip="Import a CSV file as a new table",
                        )
                    with Vertical(id="table-panel"):
                        yield MultiSelectTable(
                            id="tables",
                            cursor_type="row",
                            zebra_stripes=True,
                        )
                        yield Static("", id="tables-empty")
                    with Horizontal(id="overview-footer"):
                        yield Static(
                            "",
                            id="overview-stats",
                            classes="list-footer",
                        )
                        with Horizontal(id="overview-actions"):
                            yield Button(
                                "Open",
                                id="overview-view",
                                classes="compact-action",
                                tooltip="Open the selected table",
                            )
                            yield Button(
                                "Edit",
                                id="overview-edit",
                                classes="compact-action",
                                tooltip="Edit table metadata and columns",
                            )
                            yield Button(
                                "Export",
                                id="overview-export",
                                classes="compact-action",
                                tooltip="Export the selected table to CSV",
                            )
                            yield Button(
                                "Delete",
                                id="overview-delete",
                                classes="compact-action danger",
                                tooltip="Delete the selected table",
                            )
        yield Footer(compact=True, show_command_palette=False)

    def _tables_widget(self) -> MultiSelectTable:
        return self.query_one("#tables", MultiSelectTable)

    def _focus_overview_list(self) -> None:
        table = self._tables_widget()
        if table.display:
            _ = table.focus()
        else:
            _ = self.query_one("#overview-search", Button).focus()

    def on_mount(self) -> None:
        self._set_path_label(self.db_path)
        tabs = self._tabs_widget()
        tabs.add_tab("overview", "Tables", closable=False)
        tabs.set_active("overview")
        self._apply_layout(self.size.width)
        table = self._tables_widget()
        _ = table.add_column("Name", key="name", width=18)
        _ = table.add_column("Description", key="description", width=22)
        _ = table.add_column("Rows", key="rows", width=7)
        _ = table.add_column("Columns", key="columns", width=10)
        _ = table.add_column("Created", key="created", width=10)
        self._apply_column_widths(self.size.width)
        self._refresh_data()
        if self.storage is None:
            self._open_database_picker(
                error=self._db_error,
                missing=not self.db_path.exists(),
            )
        else:
            self._focus_overview_list()

    @on(events.Resize)
    def _resized(self, event: events.Resize) -> None:
        self._apply_layout(event.size.width)
        self._apply_column_widths(event.size.width)
        self._render_tables()

    def _apply_layout(self, width: int) -> None:
        topbar = self.query_one("#topbar", Horizontal)
        _ = topbar.set_class(width < 76, "tiny")

    def _apply_column_widths(self, width: int) -> None:
        table = self._tables_widget()
        if not table.columns:
            return
        if width >= 130:
            name_width, description_width, rows_width, created_width = 22, 34, 9, 11
        elif width >= 112:
            name_width, description_width, rows_width, created_width = 20, 30, 9, 10
        elif width >= 96:
            name_width, description_width, rows_width, created_width = 18, 24, 8, 10
        elif width >= 76:
            name_width, description_width, rows_width, created_width = 16, 18, 7, 10
        elif width >= 66:
            name_width, description_width, rows_width, created_width = 12, 10, 6, 10
        else:
            name_width, description_width, rows_width, created_width = 10, 8, 5, 10

        # the date has to stay fully visible; columns take the remaining width
        created_width = max(10, created_width)
        available = max(20, width - 18)
        columns_width = max(
            10,
            available - (name_width + description_width + rows_width + created_width),
        )
        widths = {
            "name": name_width,
            "description": description_width,
            "rows": rows_width,
            "columns": columns_width,
            "created": created_width,
        }
        for column_key, column in table.columns.items():
            key = column_key.value
            if isinstance(key, str):
                column.width = widths.get(key, column.width)
        _ = table.refresh()
        self._update_sort_labels()

    def _update_sort_labels(self) -> None:
        table = self._tables_widget()
        for column_key, column in table.columns.items():
            key = column_key.value
            if not isinstance(key, str):
                continue
            label = HEADER_LABELS.get(key, key)
            if key == self._sort_key:
                label += " ↓" if self._sort_desc else " ↑"
            column.label = Text(label)
        _ = table.refresh()

    def _set_path_label(self, path: Path) -> None:
        self.query_one("#path-label", Static).update(str(path))

    def _refresh_data(self) -> None:
        if self.storage is None:
            self._tables = []
        else:
            try:
                self._tables = self.storage.get_tables()
            except Exception as e:
                self._tables = []
                self.notify(f"Could not read catalog: {e}", severity="error")
        self._by_name = {table.name: table for table in self._tables}
        self._render_tables()

    def _render_overview_footer(self) -> None:
        stats = self.query_one("#overview-stats", Static)
        stats.display = self.size.width >= 72
        if self.storage is None:
            stats.update("")
            return

        query = self._query.strip()
        visible = self._visible_tables()
        total = len(self._tables)
        selected = self._tables_widget().selected_keys
        if selected:
            selected_tables = [
                catalog_table
                for catalog_table in self._tables
                if catalog_table.name in selected
            ]
            table_text = f"{len(selected):,} selected"
            rows = sum(catalog_table.count for catalog_table in selected_tables)
        else:
            rows = sum(catalog_table.count for catalog_table in visible)
            if query:
                table_text = f"{len(visible):,} of {total:,} tables"
            else:
                table_text = f"{total:,} {'table' if total == 1 else 'tables'}"
        row_text = f"{rows:,} {'row' if rows == 1 else 'rows'}"
        parts = [table_text]
        if self.size.width >= 76:
            parts.append(row_text)
        if self.size.width >= 96:
            parts.append(human_size(database_size(self.db_path)))
        stats.update("  ·  ".join(parts))

    def _visible_tables(self) -> list[CatalogTable]:
        query = self._query.strip().casefold()
        tables = self._tables
        if query:
            tables = [
                table
                for table in tables
                if query in table.name.casefold()
                or query in (table.description or "").casefold()
                or any(query in column.casefold() for column in table.columns)
            ]
        return sorted(tables, key=self._sort_value, reverse=self._sort_desc)

    def _sort_value(self, table: CatalogTable) -> str | int:
        if self._sort_key == "rows":
            return table.count
        if self._sort_key == "date":
            return table.created_at
        if self._sort_key == "columns":
            return len(table.columns)
        if self._sort_key == "description":
            return (table.description or "").casefold()
        return table.name.casefold()

    def _render_tables(self) -> None:
        table = self._tables_widget()
        selected = self._selected_name
        visible = self._visible_tables()
        table.retain_selection({catalog_table.name for catalog_table in visible})
        _ = table.clear(columns=False)
        empty = self.query_one("#tables-empty", Static)

        name_width = 16
        description_width = 22
        columns_width = 10
        for column_key, column in table.columns.items():
            if column_key.value == "name":
                name_width = int(column.width or name_width)
            elif column_key.value == "description":
                description_width = int(column.width or description_width)
            elif column_key.value == "columns":
                columns_width = int(column.width or columns_width)

        for catalog_table in visible:
            _ = table.add_row(
                Text(
                    truncate(catalog_table.name, max(1, name_width)),
                    style="bold #f5f5f7",
                ),
                Text(
                    truncate(
                        catalog_table.description or "—",
                        max(1, description_width),
                    ),
                    style="#d1d1d6",
                ),
                Text(f"{catalog_table.count:,}", style="#d1d1d6"),
                Text(
                    truncate(
                        ", ".join(catalog_table.columns) or "—",
                        max(1, columns_width),
                    ),
                    style="#8e8e93",
                ),
                Text(catalog_table.created_at.split("T")[0], style="#8e8e93"),
                key=catalog_table.name,
            )

        if not visible:
            table.display = False
            empty.display = True
            if self._query.strip():
                empty.update(f"No tables match “{self._query.strip()}”")
            elif self.storage is None:
                empty.update("Open a database to browse tables")
            else:
                empty.update("No tables yet · import a CSV with csvcatalog extract")
            self._select_table(None)
            self._render_overview_footer()
            return

        table.display = True
        empty.display = False
        names = {catalog_table.name for catalog_table in visible}
        selected_name = selected if selected in names else visible[0].name
        index = table.get_row_index(selected_name)
        table.move_cursor(row=index, column=0, animate=False)
        self._select_table(selected_name)
        self._render_overview_footer()

    def _select_table(self, name: str | None) -> None:
        self._selected_name = name
        self._update_overview_actions()

    def _update_overview_actions(self) -> None:
        self.query_one("#overview-import", Button).disabled = self.storage is None
        selected = self._tables_widget().selected_keys
        multi = len(selected) > 1
        has_target = bool(selected) or (
            self._selected_name is not None and self._selected_name in self._by_name
        )
        for button_id in ("overview-view", "overview-edit"):
            button = self.query_one(f"#{button_id}", Button)
            button.display = not multi
            button.disabled = not has_target
        for button_id in ("overview-delete", "overview-export"):
            self.query_one(f"#{button_id}", Button).disabled = not has_target

    @on(MultiSelectTable.SelectionChanged, "#tables")
    def _table_selection_changed(
        self, event: MultiSelectTable.SelectionChanged
    ) -> None:
        _ = event
        self._update_overview_actions()
        self._render_overview_footer()

    def _current_table(self) -> CatalogTable | None:
        if self.storage is None:
            self.notify("Open a database first", severity="warning")
            return None
        name = self._current_table_name()
        if name is None:
            self.notify("Select a table first", severity="warning")
            return None
        table = self._by_name.get(name)
        if table is None:
            self.notify("The selected table no longer exists", severity="warning")
        return table

    @on(Button.Pressed, "#overview-search")
    def _overview_search_pressed(self) -> None:
        self._open_overview_search()

    @on(Button.Pressed, "#overview-filters")
    def _overview_filters_pressed(self) -> None:
        self.action_open_filters()

    @on(Button.Pressed, "#overview-import")
    def _overview_import_pressed(self) -> None:
        self.action_import_csv()

    def action_import_csv(self) -> None:
        if self.storage is None:
            self.notify("Open a database first", severity="warning")
            return
        _ = self.push_screen(
            CsvImportWizard(self.storage, self.settings),
            self._import_finished,
        )

    def _import_finished(self, result: ImportResult | None) -> None:
        if result is None:
            return
        self._selected_name = result.table_name
        self._refresh_data()
        message = f"Imported {result.saved_rows:,} rows into '{result.table_name}'"
        if result.filtered_rows:
            message += f" · {result.filtered_rows:,} rows filtered out"
        if result.duplicates_skipped:
            message += f" · {result.duplicates_skipped:,} duplicates skipped"
        self.notify(message, severity="information")

    def _open_overview_search(self) -> None:
        _ = self.push_screen(
            SearchRowsModal(
                self._query,
                title="Search tables",
                hint="Search by table name, description or column name.",
                placeholder="Search tables…",
            ),
            self._apply_overview_search,
        )

    def _apply_overview_search(self, value: str | None) -> None:
        if value is None:
            return
        self._query = value
        self._render_tables()

    @on(Button.Pressed, "#overview-view")
    def _overview_view_pressed(self) -> None:
        self.action_view_table()

    @on(Button.Pressed, "#overview-edit")
    def _overview_edit_pressed(self) -> None:
        self.action_edit_table()

    @on(Button.Pressed, "#overview-delete")
    def _overview_delete_pressed(self) -> None:
        self.action_delete_table()

    @on(Button.Pressed, "#overview-export")
    def _overview_export_pressed(self) -> None:
        self.action_export_table()

    @on(DataTable.HeaderSelected, "#tables")
    def _header_selected(self, event: DataTable.HeaderSelected) -> None:
        column_key = event.column_key.value
        key = HEADER_SORT_KEYS.get(column_key) if isinstance(column_key, str) else None
        if key is None:
            return
        if key == self._sort_key:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_key = key
            self._sort_desc = key in ("rows", "date")
        self._render_tables()
        self._update_sort_labels()

    @on(DataTable.RowHighlighted, "#tables")
    def _row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        name = event.row_key.value
        if isinstance(name, str):
            self._select_table(name)

    @on(DataTable.RowSelected, "#tables")
    def _row_opened(self, event: DataTable.RowSelected) -> None:
        if len(self._selected_table_names()) > 1:
            return
        name = event.row_key.value
        if isinstance(name, str):
            self._open_table(name)

    @on(TableEditorView.CloseRequested)
    def _view_close_requested(self, event: TableEditorView.CloseRequested) -> None:
        self._close_table_tab(event.table_name)

    @on(TableEditorView.TableChanged)
    def _view_table_changed(self, event: TableEditorView.TableChanged) -> None:
        _ = event
        self._refresh_data()

    @on(TableEditorView.EditTableRequested)
    def _view_edit_requested(self, event: TableEditorView.EditTableRequested) -> None:
        self._edit_table_dialog(event.table_name)

    @on(TableEditorView.DeleteTableRequested)
    def _view_delete_requested(
        self, event: TableEditorView.DeleteTableRequested
    ) -> None:
        self._delete_table_dialog(event.table_name)

    @on(TableEditorView.ExportTableRequested)
    def _view_export_requested(
        self, event: TableEditorView.ExportTableRequested
    ) -> None:
        self._export_table_dialog(event.table_name)

    def _tabs_widget(self) -> EditorTabs:
        return self.query_one("#tab-bar", EditorTabs)

    def _content_widget(self) -> ContentSwitcher:
        return self.query_one("#content-switcher", ContentSwitcher)

    def _open_table(self, table_name: str) -> None:
        if self.storage is None or table_name not in self._by_name:
            return
        tabs = self._tabs_widget()
        content = self._content_widget()
        existing = self._tab_ids.get(table_name)
        if existing is not None:
            tabs.set_active(existing)
            content.current = existing
            view = self._views.get(table_name)
            if view is not None:
                view.focus_rows()
            return
        tab_id = f"table-{self._tab_counter}"
        self._tab_counter += 1
        view = TableEditorView(self.storage, table_name, id=tab_id)
        self._tab_ids[table_name] = tab_id
        self._views[table_name] = view
        _ = content.mount(view)
        tabs.add_tab(tab_id, table_name)
        tabs.set_active(tab_id)
        content.current = tab_id
        _ = self.call_after_refresh(view.focus_rows)

    @on(EditorTab.Activated)
    def _tab_activated(self, event: EditorTab.Activated) -> None:
        tabs = self._tabs_widget()
        tabs.set_active(event.tab_id)
        self._content_widget().current = event.tab_id
        if event.tab_id == "overview":
            self._focus_overview_list()
            return
        for table_name, tab_id in self._tab_ids.items():
            if tab_id == event.tab_id:
                view = self._views.get(table_name)
                if view is not None:
                    view.focus_rows()
                return

    @on(EditorTab.CloseRequested)
    def _tab_close_requested(self, event: EditorTab.CloseRequested) -> None:
        for table_name, tab_id in self._tab_ids.items():
            if tab_id == event.tab_id:
                self._close_table_tab(table_name)
                return

    def _close_table_tab(self, table_name: str) -> None:
        tab_id = self._tab_ids.pop(table_name, None)
        view = self._views.pop(table_name, None)
        if tab_id is None:
            return
        tabs = self._tabs_widget()
        content = self._content_widget()
        was_active = tabs.active_id == tab_id
        tabs.remove_tab(tab_id)
        if view is not None:
            _ = view.remove()
        if not was_active:
            return
        remaining = list(self._tab_ids.values())
        if remaining:
            next_id = remaining[-1]
            tabs.set_active(next_id)
            content.current = next_id
            next_name = next(
                name
                for name, current_id in self._tab_ids.items()
                if current_id == next_id
            )
            next_view = self._views.get(next_name)
            if next_view is not None:
                next_view.focus_rows()
        else:
            tabs.set_active("overview")
            content.current = "overview"
            self._focus_overview_list()

    def _close_all_tables(self) -> None:
        for table_name in list(self._tab_ids):
            self._close_table_tab(table_name)

    def _active_table_name(self) -> str | None:
        active = self._tabs_widget().active_id
        for table_name, tab_id in self._tab_ids.items():
            if tab_id == active:
                return table_name
        return None

    def _active_view(self) -> TableEditorView | None:
        table_name = self._active_table_name()
        if table_name is None:
            return None
        return self._views.get(table_name)

    def _current_table_name(self) -> str | None:
        active = self._active_table_name()
        if active is not None:
            return active
        selected = self._tables_widget().selected_keys
        if len(selected) == 1:
            return next(iter(selected))
        if len(selected) > 1:
            return None
        return self._selected_name

    def action_close_tab(self) -> None:
        table_name = self._active_table_name()
        if table_name is not None:
            self._close_table_tab(table_name)

    def action_request_quit(self) -> None:
        now = time.monotonic()
        if self._last_interrupt is not None and now - self._last_interrupt <= 1.5:
            self._last_interrupt = None
            self.exit()
            return
        self._last_interrupt = now
        self.notify(
            "Press Ctrl+C again to quit",
            severity="warning",
            timeout=1.5,
        )

    def action_quit_hint(self) -> None:
        self.notify("Press Ctrl+C twice to quit", severity="warning", timeout=2)

    def action_refresh_data(self) -> None:
        if self.storage is None:
            self._open_database_picker(
                error=self._db_error,
                missing=not self.db_path.exists(),
            )
            return
        self._refresh_data()
        table_name = self._active_table_name()
        if table_name is not None:
            view = self._views.get(table_name)
            if view is not None:
                view.reload()
        self.notify("Catalog refreshed", severity="information")

    def action_focus_search(self) -> None:
        table_name = self._active_table_name()
        if table_name is not None:
            view = self._views.get(table_name)
            if view is not None:
                view.open_search()
                return
        self._open_overview_search()

    def action_clear_search(self) -> None:
        table_name = self._active_table_name()
        if table_name is not None:
            view = self._views.get(table_name)
            if view is not None:
                if view.has_search():
                    view.clear_search()
                elif view.has_selection():
                    view.clear_selection()
                view.focus_rows()
                return
        if self._query:
            self._query = ""
            self._render_tables()
        elif self._tables_widget().selected_keys:
            self._tables_widget().clear_selection()
        self._focus_overview_list()

    def _open_database_picker(
        self,
        *,
        error: str | None = None,
        missing: bool = False,
        attempted_path: Path | None = None,
    ) -> None:
        path = attempted_path or self.db_path
        _ = self.push_screen(
            DatabasePickerModal(path, error=error, missing=missing),
            self._apply_database_path,
        )

    def _apply_database_path(self, path: Path | None) -> None:
        if path is None:
            if self.storage is None:
                self.exit()
            return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            new_storage = storage.SqliteStorage(path)
        except Exception as e:
            self._open_database_picker(error=str(e), attempted_path=path)
            return

        self._close_all_tables()
        if self.storage is not None:
            self.storage.close()
        self.storage = new_storage
        self.db_path = path
        self._db_error = None
        if self._on_storage_change is not None:
            self._on_storage_change(new_storage)
        if path != self.settings.db_path:
            self.settings = self.settings.model_copy(update={"db_path": path})
            config.save_config(self.settings)
        self._set_path_label(path)
        self._query = ""
        self._refresh_data()
        self.notify(f"Database opened: {path}", severity="information")
        self._focus_overview_list()

    def action_open_settings(self) -> None:
        _ = self.push_screen(SettingsModal(self.settings), self._apply_settings)

    def action_open_filters(self) -> None:
        _ = self.push_screen(FiltersModal(self.settings.filters), self._apply_filters)

    def _selected_table_names(self) -> list[str]:
        return sorted(self._tables_widget().selected_keys)

    def action_view_table(self) -> None:
        if len(self._selected_table_names()) > 1:
            return
        table = self._current_table()
        if table is None:
            return
        self._open_table(table.name)

    def action_edit_table(self) -> None:
        view = self._active_view()
        if view is not None:
            view.edit_selected_row()
            return
        self._edit_table_metadata()

    def _edit_table_metadata(self) -> None:
        if len(self._selected_table_names()) > 1:
            return
        table = self._current_table()
        if table is None:
            return
        self._edit_table_dialog(table.name)

    def _edit_table_dialog(self, table_name: str) -> None:
        table = self._by_name.get(table_name)
        if table is None:
            return
        _ = self.push_screen(
            EditTableModal(table),
            lambda patch: self._apply_table_patch(table.name, patch),
        )

    def action_export_table(self) -> None:
        if self.storage is None:
            return
        selected = self._selected_table_names()
        if len(selected) > 1:
            _ = self.push_screen(
                ExportSelectionModal(
                    title=f"Export {len(selected)} tables",
                    hint="Each table is saved as its own CSV file in this folder.",
                    default_path=Path.cwd(),
                    directory=True,
                    placeholder="~/exports",
                    button_label="Export",
                ),
                lambda path: self._export_tables(selected, path),
            )
            return
        table = self._current_table()
        if table is None:
            return
        self._export_table_dialog(table.name)

    def _export_table_dialog(self, table_name: str) -> None:
        safe_name = storage.sanitize_identifier(table_name) or "table"
        default_path = Path.cwd() / f"{safe_name}.csv"
        _ = self.push_screen(
            ExportTableModal(table_name, default_path),
            lambda path: self._export_table(table_name, path),
        )

    def _export_table(self, table_name: str, path: Path | None) -> None:
        if path is None or self.storage is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            count = self.storage.export_table_to_csv(table_name, path)
        except Exception as e:
            self.notify(f"Could not export table: {e}", severity="error")
            return
        self.notify(
            f"Exported {count:,} rows to {path}",
            severity="information",
        )

    def _export_tables(self, table_names: list[str], directory: Path | None) -> None:
        if directory is None or self.storage is None:
            return
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.notify(f"Could not create export folder: {e}", severity="error")
            return
        exported = 0
        for table_name in table_names:
            safe_name = storage.sanitize_identifier(table_name) or "table"
            path = directory / f"{safe_name}.csv"
            try:
                _ = self.storage.export_table_to_csv(table_name, path)
            except Exception as e:
                self.notify(
                    f"Could not export '{table_name}': {e}",
                    severity="error",
                )
                continue
            exported += 1
        if exported:
            table_word = "table" if exported == 1 else "tables"
            self.notify(
                f"Exported {exported:,} {table_word} to {directory}",
                severity="information",
            )

    def action_delete_table(self) -> None:
        view = self._active_view()
        if view is not None:
            view.delete_selected_rows()
            return
        self._delete_table_metadata()

    def _delete_table_metadata(self) -> None:
        selected = self._selected_table_names()
        if len(selected) > 1:
            message = (
                f"Delete {len(selected)} selected tables and all of their rows? "
                "This cannot be undone."
            )
            _ = self.push_screen(
                DeleteTableModal("Delete tables", message),
                lambda mode: self._delete_tables(selected, mode),
            )
            return
        table = self._current_table()
        if table is None:
            return
        self._delete_table_dialog(table.name)

    def _delete_table_dialog(self, table_name: str) -> None:
        _ = self.push_screen(
            DeleteTableModal(
                "Delete table",
                f"Delete '{table_name}' and all of its rows? This cannot be undone.",
            ),
            lambda mode: self._delete_table(table_name, mode),
        )

    def _apply_settings(self, settings: Settings | None) -> None:
        if settings is None:
            return
        config.save_config(settings)
        self.settings = settings
        target = settings.db_path or config.get_data_dir() / "catalog.db"
        if target != self.db_path:
            if settings.encryption:
                self.notify(
                    "Settings saved · restart to switch encrypted database",
                    severity="information",
                )
                return
            self._apply_database_path(target)
        else:
            self.notify("Settings saved", severity="information")

    def _apply_filters(self, filters: dict[str, str] | None) -> None:
        if filters is None:
            return
        self.settings = self.settings.model_copy(update={"filters": dict(filters)})
        config.save_config(self.settings)
        label = "filter" if len(filters) == 1 else "filters"
        self.notify(f"{len(filters):,} {label} saved", severity="information")

    def _apply_table_patch(self, original_name: str, patch: TablePatch | None) -> None:
        if patch is None or self.storage is None:
            return
        current = self._by_name.get(original_name)
        if current is None:
            return

        new_name = storage.sanitize_identifier(patch.name)
        if not new_name:
            self.notify("Table name cannot be empty", severity="error")
            return
        if new_name != current.name and self.storage.get_table(new_name):
            self.notify(f"Table '{new_name}' already exists", severity="error")
            return

        was_open = original_name in self._tab_ids
        try:
            if new_name != current.name:
                self.storage.rename_table(current.name, new_name)
            if patch.description != (current.description or ""):
                self.storage.update_description(new_name, patch.description)
            if patch.created_at != current.created_at:
                self.storage.update_created_at(new_name, patch.created_at)
            self._apply_columns_patch(new_name, patch.columns)
        except Exception as e:
            self.notify(f"Could not update table: {e}", severity="error")
            self._refresh_data()
            return

        self._selected_name = new_name
        if was_open and new_name != original_name:
            self._close_table_tab(original_name)
            self._refresh_data()
            self._open_table(new_name)
        else:
            self._refresh_data()
            view = self._views.get(new_name)
            if view is not None:
                view.reload()
        self.notify(f"Table '{new_name}' updated", severity="information")

    def _apply_columns_patch(self, table_name: str, patch: ColumnsPatch) -> None:
        if self.storage is None:
            return
        for column in patch.deletions:
            self.storage.delete_column(table_name, column)
        for old_name, new_name in patch.renames.items():
            self.storage.rename_column(table_name, old_name, new_name)

    def _delete_table(self, name: str, mode: str | None) -> None:
        if mode is None or self.storage is None:
            return
        try:
            self.storage.delete_table(name)
            if mode == "compact":
                self.notify("Compacting database...", severity="information")
                self.storage.compact_database()
        except Exception as e:
            self.notify(f"Could not delete table: {e}", severity="error")
            return
        self._close_table_tab(name)
        if self._selected_name == name:
            self._selected_name = None
        self._refresh_data()
        suffix = " · database compacted" if mode == "compact" else ""
        self.notify(f"Table '{name}' deleted{suffix}", severity="information")

    def _delete_tables(self, names: list[str], mode: str | None) -> None:
        if mode is None or self.storage is None:
            return
        deleted = 0
        for name in names:
            try:
                self.storage.delete_table(name)
            except Exception as e:
                self.notify(f"Could not delete '{name}': {e}", severity="error")
                continue
            self._close_table_tab(name)
            deleted += 1
        if deleted and mode == "compact":
            try:
                self.notify("Compacting database...", severity="information")
                self.storage.compact_database()
            except Exception as e:
                self.notify(f"Could not compact database: {e}", severity="error")
        if self._selected_name in names:
            self._selected_name = None
        self._tables_widget().clear_selection()
        self._refresh_data()
        if deleted:
            suffix = " · database compacted" if mode == "compact" else ""
            self.notify(
                f"Deleted {deleted:,} {'table' if deleted == 1 else 'tables'}{suffix}",
                severity="information",
            )
