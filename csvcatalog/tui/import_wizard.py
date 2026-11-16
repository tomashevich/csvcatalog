import asyncio
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast, final, override

from rich.text import Text
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import (
    Container,
    Horizontal,
    HorizontalScroll,
    Vertical,
)
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    ContentSwitcher,
    DataTable,
    Input,
    Label,
    LoadingIndicator,
    Select,
    SelectionList,
    Static,
)
from textual.widgets.selection_list import Selection

from .. import config, storage
from ..config import Settings
from ..storage import BaseStorage
from .format import truncate
from .widgets import PathField

BATCH_SIZE = 10_000
STEP_IDS = (
    "import-source",
    "import-columns",
    "import-mapping",
    "import-filters",
    "import-unique",
    "import-details",
    "import-review",
    "import-progress",
)
STEP_TITLES = (
    "Source",
    "Columns",
    "Mapping",
    "Filters",
    "Unique",
    "Details",
    "Review",
    "Import",
)


@dataclass(frozen=True)
class ImportResult:
    """successful import summary"""

    table_name: str
    saved_rows: int
    filtered_rows: int
    duplicates_skipped: int = 0


@final
class CsvImportWizard(Screen[ImportResult | None]):
    """full-screen multi-step csv import wizard matching the extract command"""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("s,ы", "noop", "Settings", show=False),
        Binding("f,а", "noop", "Filters", show=False),
        Binding("i,ш", "noop", "Import", show=False),
        Binding("r,к,ctrl+r", "noop", "Refresh", show=False),
        Binding("e,у,ctrl+e", "noop", "Edit", show=False),
        Binding("d,в", "noop", "Delete", show=False),
        Binding("/,.,ctrl+f", "noop", "Search", show=False),
        Binding("ctrl+w", "noop", "Close tab", show=False),
    ]

    def __init__(
        self,
        storage_instance: BaseStorage,
        settings: Settings,
    ) -> None:
        super().__init__(classes="import-screen")
        self.storage = storage_instance
        self.settings = settings
        self._step_index = 0
        self._importing = False
        self._file_path: Path | None = None
        self._encoding = "utf-8"
        self._separator = ","
        self._headers: list[str] = []
        self._preview_rows: list[list[str]] = []
        self._selected_headers: list[str] = []
        self._column_map: dict[str, str] = {}
        self._filters: dict[str, list[str]] = {}
        self._filter_rows: list[tuple[str, str]] = []
        self._unique_columns: list[str] = []
        self._table_name = ""
        self._description = ""
        self._mapping_selected: str | None = None

    @override
    def compose(self) -> ComposeResult:
        with Container(classes="import-screen-body"):
            with Horizontal(id="import-header"):
                yield Static("Import CSV", classes="modal-title")
                yield Static("", id="import-step-label")
            with ContentSwitcher(initial=STEP_IDS[0], id="import-steps"):
                with Vertical(id="import-source", classes="import-step-body"):
                    yield Static(
                        "Choose a CSV file. Check that the preview looks correct.",
                        classes="modal-hint",
                    )
                    yield Label("CSV file", classes="form-label")
                    yield PathField(
                        placeholder="~/data.csv",
                        suffixes=frozenset({".csv"}),
                        id="import-path",
                    )
                    with Horizontal(classes="form-row"):
                        yield Label("Encoding", classes="form-label")
                        yield Input(value="utf-8", id="import-encoding")
                    with Horizontal(classes="form-row"):
                        yield Label("Separator", classes="form-label")
                        yield Input(
                            value=",",
                            placeholder=", or \\t",
                            id="import-separator",
                        )
                    with Horizontal(classes="form-row compact form-actions"):
                        yield Button(
                            "Refresh preview",
                            id="import-refresh",
                            classes="compact-action accent",
                        )
                    yield Static("", id="import-source-status", markup=False)
                    yield DataTable(
                        id="import-preview",
                        cursor_type="none",
                        zebra_stripes=True,
                    )
                    yield Static(
                        "First 5 rows are shown. Use \\t for a tab separator.",
                        classes="form-note",
                    )

                with Vertical(id="import-columns", classes="import-step-body"):
                    yield Static(
                        "Select the CSV columns to import.",
                        classes="modal-hint",
                    )
                    with Horizontal(classes="form-row compact form-actions"):
                        yield Button(
                            "All",
                            id="import-columns-all",
                            classes="compact-action",
                        )
                        yield Button(
                            "None",
                            id="import-columns-none",
                            classes="compact-action",
                        )
                        yield Static("", id="import-columns-count")
                    yield SelectionList(id="import-column-list", compact=True)

                with Vertical(id="import-mapping", classes="import-step-body"):
                    yield Static(
                        "Set database column names. Select a row and rename it.",
                        classes="modal-hint",
                    )
                    yield DataTable(
                        id="import-mapping-table",
                        cursor_type="row",
                        zebra_stripes=True,
                    )
                    yield Label("Database name", classes="form-label")
                    yield Input(id="import-mapping-name")
                    with Horizontal(classes="form-row compact form-actions"):
                        yield Button(
                            "Rename",
                            id="import-mapping-rename",
                            classes="compact-action accent",
                        )
                        yield Static("", id="import-mapping-status")
                    yield Static(
                        "Names are sanitized automatically.",
                        classes="form-note",
                    )

                with Vertical(id="import-filters", classes="import-step-body"):
                    yield Static(
                        "Optional regex filters. A row must match every regex on every filtered column.",
                        classes="modal-hint",
                    )
                    yield DataTable(
                        id="import-filter-table",
                        cursor_type="row",
                        zebra_stripes=True,
                    )
                    with Horizontal(classes="form-row"):
                        yield Label("Column", classes="form-label")
                        yield Select(
                            [],
                            prompt="Choose column",
                            allow_blank=True,
                            id="import-filter-column",
                        )
                    with Horizontal(classes="form-row"):
                        yield Label("Saved filter", classes="form-label")
                        yield Select(
                            [],
                            prompt="New regex",
                            allow_blank=True,
                            id="import-filter-saved",
                        )
                    with Horizontal(classes="form-row"):
                        yield Label("Regex", classes="form-label")
                        yield Input(
                            placeholder="Regular expression",
                            id="import-filter-regex",
                        )
                    with Horizontal(classes="form-row"):
                        yield Label("Filter name", classes="form-label")
                        yield Input(
                            placeholder="Name to save as a reusable filter",
                            id="import-filter-name",
                        )
                    with Horizontal(classes="form-row compact form-actions"):
                        yield Checkbox(
                            "Save as reusable filter",
                            id="import-filter-save",
                            compact=True,
                        )
                        yield Button(
                            "Add filter",
                            id="import-filter-add",
                            classes="compact-action accent",
                        )
                        yield Button(
                            "Remove selected",
                            id="import-filter-remove",
                            classes="compact-action danger",
                        )
                    yield Static("", id="import-filter-status")

                with Vertical(id="import-unique", classes="import-step-body"):
                    yield Static(
                        "Optionally select columns whose combination must be unique. The first occurrence is kept.",
                        classes="modal-hint",
                    )
                    with Horizontal(classes="form-row compact form-actions"):
                        yield Button(
                            "All",
                            id="import-unique-all",
                            classes="compact-action",
                        )
                        yield Button(
                            "None",
                            id="import-unique-none",
                            classes="compact-action",
                        )
                        yield Static("", id="import-unique-count")
                    yield SelectionList(id="import-unique-list", compact=True)
                    yield Static(
                        "Selected columns form one combined uniqueness key.",
                        classes="form-note",
                    )

                with Vertical(id="import-details", classes="import-step-body"):
                    yield Static(
                        "Give the new table a name and optional description.",
                        classes="modal-hint",
                    )
                    yield Label("Table name", classes="form-label")
                    yield Input(id="import-table-name")
                    yield Static("", id="import-table-name-note")
                    yield Label("Description", classes="form-label")
                    yield Input(
                        placeholder="Optional description",
                        id="import-description",
                    )
                    yield Static(
                        "Leave the description empty to skip it.",
                        classes="form-note",
                    )

                with Vertical(id="import-review", classes="import-step-body"):
                    yield Static(
                        "Review the import settings before writing to the database.",
                        classes="modal-hint",
                    )
                    yield Static("", id="import-summary", markup=False)
                    yield DataTable(
                        id="import-review-preview",
                        cursor_type="none",
                        zebra_stripes=True,
                    )
                    yield Static("", id="import-review-note")

                with Vertical(id="import-progress", classes="import-step-body"):
                    yield LoadingIndicator()
                    yield Static("Preparing import…", id="import-status")
                    yield Static("", id="import-progress-note")

            with HorizontalScroll(classes="modal-actions"):
                yield Button("Cancel", id="import-cancel")
                yield Button("Back", id="import-back")
                yield Button("Next", id="import-next", variant="primary")

    def on_mount(self) -> None:
        self._set_step(0)

    def _set_step(self, index: int) -> None:
        self._step_index = index
        self.query_one("#import-steps", ContentSwitcher).current = STEP_IDS[index]
        self.query_one("#import-step-label", Static).update(
            f"{index + 1}/{len(STEP_IDS)} · {STEP_TITLES[index]}"
        )
        back = self.query_one("#import-back", Button)
        next_button = self.query_one("#import-next", Button)
        cancel = self.query_one("#import-cancel", Button)
        back.display = 0 < index < len(STEP_IDS) - 1
        next_button.display = index != len(STEP_IDS) - 1
        next_button.label = "Import" if index == len(STEP_IDS) - 2 else "Next"
        cancel.disabled = index == len(STEP_IDS) - 1
        if index == 1:
            self._prepare_columns()
        elif index == 2:
            self._prepare_mapping()
        elif index == 3:
            self._prepare_filters()
        elif index == 4:
            self._prepare_unique()
        elif index == 5:
            self._prepare_details()
        elif index == 6:
            self._prepare_review()

    @on(Button.Pressed, "#import-cancel")
    def _cancel_pressed(self) -> None:
        self.action_cancel()

    @on(Button.Pressed, "#import-back")
    def _back_pressed(self) -> None:
        if self._importing or self._step_index == 0:
            return
        if self._step_index == 1:
            _ = self._collect_columns(validate=False)
        elif self._step_index == 4:
            _ = self._collect_unique()
        elif self._step_index == 5:
            _ = self._collect_details(validate=False)
        self._set_step(self._step_index - 1)

    @on(Button.Pressed, "#import-next")
    def _next_pressed(self) -> None:
        self._next()

    def _next(self) -> None:
        if self._importing:
            return
        if self._step_index == 0 and not self._load_source():
            return
        elif self._step_index == 1 and not self._collect_columns(validate=True):
            return
        elif self._step_index == 2 and not self._validate_mapping():
            return
        elif self._step_index == 4 and not self._collect_unique():
            return
        elif self._step_index == 5 and not self._collect_details(validate=True):
            return
        elif self._step_index == 6:
            self._start_import()
            return
        self._set_step(self._step_index + 1)

    @on(Button.Pressed, "#import-refresh")
    def _refresh_preview(self) -> None:
        _ = self._load_source()

    def _normalize_separator(self, raw: str) -> str | None:
        if raw in ("\\t", "tab", "TAB"):
            return "\t"
        if len(raw) != 1:
            self.notify("Separator must be one character", severity="error")
            return None
        return raw

    def _load_source(self) -> bool:
        path_field = self.query_one("#import-path", PathField)
        path_field.hide_suggestions()
        raw_path = path_field.value.strip()
        if not raw_path:
            self.notify("CSV path cannot be empty", severity="error")
            return False
        path = Path(raw_path).expanduser()
        if not path.exists() or not path.is_file():
            self.notify("CSV file was not found", severity="error")
            return False
        separator = self._normalize_separator(
            self.query_one("#import-separator", Input).value
        )
        if separator is None:
            return False
        encoding = self.query_one("#import-encoding", Input).value.strip() or "utf-8"
        try:
            with path.open("r", encoding=encoding, newline="") as csv_file:
                reader = csv.reader(csv_file, delimiter=separator)
                headers = next(reader)
                preview: list[list[str]] = []
                for index, row in enumerate(reader):
                    if index >= 5:
                        break
                    preview.append(row)
        except StopIteration:
            self.notify("CSV file is empty", severity="error")
            return False
        except LookupError:
            self.notify(f"Unknown encoding: {encoding}", severity="error")
            return False
        except UnicodeDecodeError as e:
            self.notify(
                f"Could not decode file with '{encoding}': {e}",
                severity="error",
            )
            return False
        except (OSError, csv.Error) as e:
            self.notify(f"Could not read CSV file: {e}", severity="error")
            return False

        if not headers:
            self.notify("CSV file has no columns", severity="error")
            return False
        if any(not header.strip() for header in headers):
            self.notify("CSV has an empty column name", severity="error")
            return False
        if len(set(headers)) != len(headers):
            self.notify("CSV has duplicate column names", severity="error")
            return False

        changed = (path, encoding, separator) != (
            self._file_path,
            self._encoding,
            self._separator,
        )
        self._file_path = path
        self._encoding = encoding
        self._separator = separator
        self._headers = headers
        self._preview_rows = preview
        if changed:
            self._selected_headers = list(headers)
            self._column_map = {
                header: storage.sanitize_identifier(header) for header in headers
            }
            self._filters = {}
            self._unique_columns = []
            default_name = storage.sanitize_identifier(path.stem) or "table"
            self._table_name = default_name
            self._description = ""
        self._render_source_preview()
        status = f"{len(headers)} columns · {len(preview)} preview rows"
        if not preview:
            status += " · no data rows found"
        self.query_one("#import-source-status", Static).update(status)
        return True

    def _preview_column_width(self, column_count: int) -> int:
        width = (
            self.size.width
            if self.size.width > 20
            else cast(App[None], self.app).size.width
        )
        available = max(24, width - 10)
        return max(8, min(28, available // max(1, column_count) - 3))

    def _render_source_preview(self) -> None:
        table = cast(DataTable[Text], self.query_one("#import-preview", DataTable))
        _ = table.clear(columns=True)
        width = self._preview_column_width(len(self._headers))
        for index, header in enumerate(self._headers):
            _ = table.add_column(
                Text(truncate(header, width)),
                key=str(index),
                width=width,
            )
        for row in self._preview_rows:
            padded = list(row[: len(self._headers)])
            padded.extend([""] * (len(self._headers) - len(padded)))
            _ = table.add_row(*[Text(truncate(value, width)) for value in padded])
        _ = table.refresh()

    @on(events.Resize)
    def _resized(self, event: events.Resize) -> None:
        _ = event
        if self._headers:
            self._render_source_preview()
        if self._step_index == 6:
            self._prepare_review()

    def _prepare_columns(self) -> None:
        selection_list = cast(
            SelectionList[str],
            self.query_one("#import-column-list", SelectionList),
        )
        _ = selection_list.clear_options()
        selected = set(self._selected_headers or self._headers)
        _ = selection_list.add_options(
            [
                Selection(
                    header,
                    header,
                    initial_state=header in selected,
                )
                for header in self._headers
            ]
        )
        self._update_columns_count()
        _ = selection_list.focus()

    def _update_columns_count(self) -> None:
        selection_list = cast(
            SelectionList[str],
            self.query_one("#import-column-list", SelectionList),
        )
        count = len(selection_list.selected)
        self.query_one("#import-columns-count", Static).update(
            f"{count} of {len(self._headers)} selected"
        )

    @on(SelectionList.SelectedChanged, "#import-column-list")
    def _column_selection_changed(
        self, event: SelectionList.SelectedChanged[str]
    ) -> None:
        _ = event
        self._update_columns_count()

    @on(Button.Pressed, "#import-columns-all")
    def _select_all_columns(self) -> None:
        selection_list = cast(
            SelectionList[str],
            self.query_one("#import-column-list", SelectionList),
        )
        _ = selection_list.select_all()
        self._update_columns_count()

    @on(Button.Pressed, "#import-columns-none")
    def _select_no_columns(self) -> None:
        selection_list = cast(
            SelectionList[str],
            self.query_one("#import-column-list", SelectionList),
        )
        _ = selection_list.deselect_all()
        self._update_columns_count()

    def _collect_columns(self, *, validate: bool) -> bool:
        selection_list = cast(
            SelectionList[str],
            self.query_one("#import-column-list", SelectionList),
        )
        selected = set(selection_list.selected)
        ordered = [header for header in self._headers if header in selected]
        if validate and not ordered:
            self.notify("Select at least one column", severity="error")
            return False
        if ordered:
            self._selected_headers = ordered
        for header in self._selected_headers:
            _ = self._column_map.setdefault(header, storage.sanitize_identifier(header))
        mapped = {self._column_map[header] for header in self._selected_headers}
        self._filters = {
            column: patterns
            for column, patterns in self._filters.items()
            if column in mapped
        }
        self._unique_columns = [
            column for column in self._unique_columns if column in mapped
        ]
        return True

    def _prepare_mapping(self) -> None:
        table = cast(
            DataTable[Text],
            self.query_one("#import-mapping-table", DataTable),
        )
        _ = table.clear(columns=True)
        _ = table.add_column("CSV column", key="csv", width=24)
        _ = table.add_column("Database column", key="mapped")
        for header in self._selected_headers:
            mapped = self._column_map.get(header, storage.sanitize_identifier(header))
            self._column_map[header] = mapped
            _ = table.add_row(
                Text(header),
                Text(mapped),
                key=header,
            )
        if self._selected_headers:
            table.move_cursor(row=0, column=0, animate=False)
            self._load_mapping_name(self._selected_headers[0])
            _ = table.focus()
        self.query_one("#import-mapping-status", Static).update("")

    def _load_mapping_name(self, header: str) -> None:
        self._mapping_selected = header
        mapped = self._column_map.get(header, "")
        self.query_one("#import-mapping-name", Input).value = mapped

    @on(DataTable.RowHighlighted, "#import-mapping-table")
    def _mapping_highlighted(self, event: DataTable.RowHighlighted) -> None:
        header = event.row_key.value
        if isinstance(header, str):
            self._load_mapping_name(header)

    @on(Button.Pressed, "#import-mapping-rename")
    def _rename_mapping(self) -> None:
        if self._mapping_selected is None:
            self.notify("Select a column first", severity="warning")
            return
        raw = self.query_one("#import-mapping-name", Input).value.strip()
        if not raw:
            self.notify("Column name cannot be empty", severity="error")
            return
        mapped = storage.sanitize_identifier(raw)
        used = {
            self._column_map[header]
            for header in self._selected_headers
            if header != self._mapping_selected
        }
        if mapped in used:
            self.notify(f"Column '{mapped}' already exists", severity="error")
            return
        old_name = self._column_map[self._mapping_selected]
        self._column_map[self._mapping_selected] = mapped
        if old_name in self._filters:
            self._filters[mapped] = self._filters.pop(old_name)
        if old_name in self._unique_columns:
            index = self._unique_columns.index(old_name)
            self._unique_columns[index] = mapped
        cast(
            DataTable[Text],
            self.query_one("#import-mapping-table", DataTable),
        ).update_cell(
            self._mapping_selected,
            "mapped",
            Text(mapped),
        )
        status = ""
        if mapped != raw:
            status = f"Sanitized to '{mapped}'"
        self.query_one("#import-mapping-status", Static).update(status)

    def _validate_mapping(self) -> bool:
        names = [self._column_map.get(header, "") for header in self._selected_headers]
        if any(not name for name in names):
            self.notify("Column names cannot be empty", severity="error")
            return False
        if len(set(names)) != len(names):
            self.notify("Database column names must be unique", severity="error")
            return False
        return True

    def _prepare_filters(self) -> None:
        columns = [self._column_map[header] for header in self._selected_headers]
        column_select = cast(
            Select[str],
            self.query_one("#import-filter-column", Select),
        )
        column_select.set_options([(column, column) for column in columns])
        if columns:
            column_select.value = columns[0]
        saved_select = cast(
            Select[str],
            self.query_one("#import-filter-saved", Select),
        )
        saved_select.set_options(
            [(name, name) for name in sorted(self.settings.filters)]
        )
        self._render_filters()
        self.query_one("#import-filter-regex", Input).value = ""
        self.query_one("#import-filter-name", Input).value = ""
        self.query_one("#import-filter-save", Checkbox).value = False
        self.query_one("#import-filter-status", Static).update("")

    def _render_filters(self) -> None:
        table = cast(
            DataTable[Text],
            self.query_one("#import-filter-table", DataTable),
        )
        _ = table.clear(columns=True)
        _ = table.add_column("Column", key="column", width=24)
        _ = table.add_column("Regex", key="regex")
        self._filter_rows = []
        for column, patterns in self._filters.items():
            for pattern in patterns:
                index = len(self._filter_rows)
                _ = table.add_row(
                    Text(column),
                    Text(pattern),
                    key=str(index),
                )
                self._filter_rows.append((column, pattern))
        _ = table.refresh()

    @on(Select.Changed, "#import-filter-saved")
    def _saved_filter_changed(self, event: Select.Changed) -> None:
        if isinstance(event.value, str) and event.value:
            self.query_one(
                "#import-filter-regex", Input
            ).value = self.settings.filters.get(event.value, "")

    @on(Button.Pressed, "#import-filter-add")
    def _add_filter(self) -> None:
        column_value = cast(
            Select[str],
            self.query_one("#import-filter-column", Select),
        ).value
        if not isinstance(column_value, str):
            self.notify("Choose a column", severity="error")
            return
        pattern = self.query_one("#import-filter-regex", Input).value.strip()
        saved_value = cast(
            Select[str],
            self.query_one("#import-filter-saved", Select),
        ).value
        if not pattern and isinstance(saved_value, str):
            pattern = self.settings.filters.get(saved_value, "")
        if not pattern:
            self.notify("Regex pattern cannot be empty", severity="error")
            return
        try:
            _ = re.compile(pattern)
        except re.error as e:
            self.notify(f"Invalid regex: {e}", severity="error")
            return
        save_filter = self.query_one("#import-filter-save", Checkbox).value
        filter_name = self.query_one("#import-filter-name", Input).value.strip()
        if save_filter and not filter_name:
            self.notify("Filter name cannot be empty", severity="error")
            return
        patterns = self._filters.setdefault(column_value, [])
        if pattern not in patterns:
            patterns.append(pattern)
        if save_filter:
            self.settings.filters[filter_name] = pattern
            config.save_config(self.settings)
            cast(
                Select[str],
                self.query_one("#import-filter-saved", Select),
            ).set_options([(key, key) for key in sorted(self.settings.filters)])
            self.notify(f"Filter '{filter_name}' saved", severity="information")
        self.query_one("#import-filter-regex", Input).value = ""
        self.query_one("#import-filter-name", Input).value = ""
        self.query_one("#import-filter-save", Checkbox).value = False
        self._render_filters()
        total = sum(len(items) for items in self._filters.values())
        self.query_one("#import-filter-status", Static).update(f"{total} filter(s)")

    @on(Button.Pressed, "#import-filter-remove")
    def _remove_filter(self) -> None:
        table = cast(
            DataTable[Text],
            self.query_one("#import-filter-table", DataTable),
        )
        row = table.cursor_coordinate.row
        if row < 0 or row >= len(self._filter_rows):
            self.notify("Select a filter to remove", severity="warning")
            return
        column, pattern = self._filter_rows[row]
        patterns = self._filters.get(column, [])
        if pattern in patterns:
            patterns.remove(pattern)
        if not patterns:
            _ = self._filters.pop(column, None)
        self.query_one("#import-filter-status", Static).update("")
        self._render_filters()

    def _prepare_unique(self) -> None:
        columns = [self._column_map[header] for header in self._selected_headers]
        selection_list = cast(
            SelectionList[str],
            self.query_one("#import-unique-list", SelectionList),
        )
        _ = selection_list.clear_options()
        selected = set(self._unique_columns)
        _ = selection_list.add_options(
            [
                Selection(
                    column,
                    column,
                    initial_state=column in selected,
                )
                for column in columns
            ]
        )
        _ = selection_list.focus()
        self._update_unique_count()

    def _update_unique_count(self) -> None:
        selection_list = cast(
            SelectionList[str],
            self.query_one("#import-unique-list", SelectionList),
        )
        count = len(selection_list.selected)
        if count:
            text = f"{count} {'column' if count == 1 else 'columns'} selected"
        else:
            text = "Duplicate checking off"
        self.query_one("#import-unique-count", Static).update(text)

    @on(SelectionList.SelectedChanged, "#import-unique-list")
    def _unique_selection_changed(
        self, event: SelectionList.SelectedChanged[str]
    ) -> None:
        _ = event
        self._update_unique_count()

    @on(Button.Pressed, "#import-unique-all")
    def _select_all_unique(self) -> None:
        selection_list = cast(
            SelectionList[str],
            self.query_one("#import-unique-list", SelectionList),
        )
        _ = selection_list.select_all()
        self._update_unique_count()

    @on(Button.Pressed, "#import-unique-none")
    def _select_no_unique(self) -> None:
        selection_list = cast(
            SelectionList[str],
            self.query_one("#import-unique-list", SelectionList),
        )
        _ = selection_list.deselect_all()
        self._update_unique_count()

    def _collect_unique(self) -> bool:
        selection_list = cast(
            SelectionList[str],
            self.query_one("#import-unique-list", SelectionList),
        )
        selected = set(selection_list.selected)
        mapped = [self._column_map[header] for header in self._selected_headers]
        self._unique_columns = [column for column in mapped if column in selected]
        return True

    def _prepare_details(self) -> None:
        name = self._table_name or (
            storage.sanitize_identifier(self._file_path.stem)
            if self._file_path is not None
            else ""
        )
        self.query_one("#import-table-name", Input).value = name
        self.query_one("#import-description", Input).value = self._description
        self._update_table_name_note()
        _ = self.query_one("#import-table-name", Input).focus()

    @on(Input.Changed, "#import-table-name")
    def _table_name_changed(self, event: Input.Changed) -> None:
        _ = event
        self._update_table_name_note()

    def _update_table_name_note(self) -> None:
        raw = self.query_one("#import-table-name", Input).value.strip()
        sanitized = storage.sanitize_identifier(raw)
        note = ""
        if raw and sanitized != raw:
            note = f"Will be saved as '{sanitized}'"
        self.query_one("#import-table-name-note", Static).update(note)

    def _collect_details(self, *, validate: bool) -> bool:
        raw_name = self.query_one("#import-table-name", Input).value.strip()
        name = storage.sanitize_identifier(raw_name)
        if validate:
            if not name:
                self.notify("Table name cannot be empty", severity="error")
                return False
            if self.storage.get_table(name) is not None:
                self.notify(f"Table '{name}' already exists", severity="error")
                return False
        if name:
            self._table_name = name
        self._description = self.query_one("#import-description", Input).value.strip()
        return True

    def _build_preview_rows(self) -> list[dict[str, str]]:
        header_index = {header: index for index, header in enumerate(self._headers)}
        rows: list[dict[str, str]] = []
        seen: set[tuple[str, ...]] = set()
        for line in self._preview_rows:
            row_data: dict[str, str] = {}
            for header in self._selected_headers:
                index = header_index.get(header)
                if index is None or index >= len(line):
                    continue
                row_data[self._column_map[header]] = line[index]
            if not row_data or self._row_is_filtered_out(row_data):
                continue
            if self._unique_columns:
                key = tuple(row_data.get(column, "") for column in self._unique_columns)
                if key in seen:
                    continue
                seen.add(key)
            rows.append(row_data)
        return rows

    def _row_is_filtered_out(self, row_data: dict[str, str]) -> bool:
        for column, patterns in self._filters.items():
            value = row_data.get(column, "")
            if not all(re.search(pattern, value) for pattern in patterns):
                return True
        return False

    def _prepare_review(self) -> None:
        if self._file_path is None:
            return
        separator = "\\t" if self._separator == "\t" else self._separator
        lines = [
            f"File:        {self._file_path}",
            f"Encoding:    {self._encoding}",
            f"Separator:   {separator}",
            f"Table:       {self._table_name}",
            f"Description: {self._description or '—'}",
            "",
            "Column mapping:",
        ]
        for header in self._selected_headers:
            lines.append(f"  {header} -> {self._column_map[header]}")
        lines.append("")
        if self._filters:
            lines.append("Filters:")
            for column, patterns in self._filters.items():
                for pattern in patterns:
                    lines.append(f"  {column} must match {pattern}")
        else:
            lines.append("Filters: none")
        lines.append("")
        if self._unique_columns:
            lines.append(
                "Unique by:    "
                + " + ".join(self._unique_columns)
                + "  (first occurrence kept)"
            )
        else:
            lines.append("Unique by:    none")
        self.query_one("#import-summary", Static).update("\n".join(lines))

        preview = self._build_preview_rows()
        table = cast(
            DataTable[Text],
            self.query_one("#import-review-preview", DataTable),
        )
        _ = table.clear(columns=True)
        mapped_columns = [self._column_map[h] for h in self._selected_headers]
        width = self._preview_column_width(len(mapped_columns))
        for column in mapped_columns:
            _ = table.add_column(
                Text(truncate(column, width)),
                key=column,
                width=width,
            )
        for row in preview:
            _ = table.add_row(
                *[
                    Text(truncate(row.get(column, ""), width))
                    for column in mapped_columns
                ]
            )
        note = self.query_one("#import-review-note", Static)
        if preview:
            note.update("Preview: first 5 rows after filters and duplicate checks.")
        else:
            note.update("Preview: no preview rows match the filters.")

    def _start_import(self) -> None:
        if self._file_path is None:
            return
        if self.storage.get_table(self._table_name) is not None:
            self.notify(
                f"Table '{self._table_name}' already exists",
                severity="error",
            )
            self._set_step(5)
            return
        self._importing = True
        self._set_step(len(STEP_IDS) - 1)
        self.query_one("#import-status", Static).update("Importing…")
        self.query_one("#import-progress-note", Static).update("")
        _ = self._perform_import()

    def _update_progress(self, saved: int, filtered: int, duplicates: int) -> None:
        text = f"Saved {saved:,} rows · filtered out {filtered:,}"
        if self._unique_columns:
            text += f" · duplicates skipped {duplicates:,}"
        self.query_one("#import-status", Static).update(text)

    @work(exclusive=True)
    async def _perform_import(self) -> None:
        if self._file_path is None:
            return
        columns = [self._column_map[header] for header in self._selected_headers]
        header_index = {header: index for index, header in enumerate(self._headers)}
        created = False
        saved = 0
        filtered = 0
        duplicates = 0
        seen: set[tuple[str, ...]] = set()
        try:
            self.storage.create_table(self._table_name, columns)
            created = True
            if self._description:
                self.storage.update_description(
                    self._table_name,
                    self._description,
                )
            with self._file_path.open(
                "r",
                encoding=self._encoding,
                newline="",
            ) as csv_file:
                reader = csv.reader(csv_file, delimiter=self._separator)
                _ = next(reader)
                batch: list[dict[str, str]] = []
                for row_parts in reader:
                    if not row_parts:
                        continue
                    row_data: dict[str, str] = {}
                    for header in self._selected_headers:
                        index = header_index.get(header)
                        if index is None or index >= len(row_parts):
                            continue
                        row_data[self._column_map[header]] = row_parts[index]
                    if not row_data:
                        continue
                    if self._row_is_filtered_out(row_data):
                        filtered += 1
                        continue
                    if self._unique_columns:
                        unique_key = tuple(
                            row_data.get(column, "") for column in self._unique_columns
                        )
                        if unique_key in seen:
                            duplicates += 1
                            continue
                        seen.add(unique_key)
                    batch.append(row_data)
                    if len(batch) < BATCH_SIZE:
                        continue
                    self.storage.save(self._table_name, batch)
                    saved += len(batch)
                    batch.clear()
                    self._update_progress(saved, filtered, duplicates)
                    await asyncio.sleep(0)
                if batch:
                    self.storage.save(self._table_name, batch)
                    saved += len(batch)
                    self._update_progress(saved, filtered, duplicates)
            self._importing = False
            _ = self.dismiss(
                ImportResult(
                    table_name=self._table_name,
                    saved_rows=saved,
                    filtered_rows=filtered,
                    duplicates_skipped=duplicates,
                )
            )
        except Exception as e:
            if created:
                try:
                    self.storage.delete_table(self._table_name)
                except Exception:
                    pass
            self._importing = False
            self.notify(f"Import failed: {e}", severity="error")
            _ = self.dismiss(None)

    def action_cancel(self) -> None:
        if self._importing:
            return
        _ = self.dismiss(None)

    def action_noop(self) -> None:
        """block app-wide shortcuts while the import screen is open"""
