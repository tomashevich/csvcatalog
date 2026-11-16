import time
from typing import cast, final, override

from rich.color import Color
from rich.style import Style
from textual import events, on
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable
from textual.widgets.data_table import CursorType

SELECTED_BACKGROUND = Color.parse("#123a5c")
SELECTED_FOREGROUND = Color.parse("#ffffff")


@final
class MultiSelectTable(DataTable[object]):
    """data table with explorer-style ctrl/shift multi-selection"""

    BINDINGS = [
        Binding("space", "toggle_cursor_selection", "Select", show=False),
        Binding("ctrl+a", "select_all_visible", "Select all", show=False),
        Binding("shift+up", "extend_selection_up", "Extend selection", show=False),
        Binding("shift+down", "extend_selection_down", "Extend selection", show=False),
    ]

    class SelectionChanged(Message):
        """posted whenever the set of selected row keys changes"""

        _table: Widget
        selected_keys: frozenset[str]

        def __init__(
            self,
            table: Widget,
            selected_keys: frozenset[str],
        ) -> None:
            self._table = table
            self.selected_keys = selected_keys
            super().__init__()

        @property
        @override
        def control(self) -> Widget:
            return self._table

    def __init__(
        self,
        *,
        id: str | None = None,
        cursor_type: CursorType = "row",
        zebra_stripes: bool = False,
    ) -> None:
        super().__init__(
            id=id,
            cursor_type=cursor_type,
            zebra_stripes=zebra_stripes,
        )
        self._selected_keys: set[str] = set()
        self._anchor_key: str | None = None
        self._last_click_key: str | None = None
        self._last_click_at = 0.0
        self._mouse_down_shift = False
        self._mouse_down_ctrl = False

    @property
    def selected_keys(self) -> frozenset[str]:
        return frozenset(self._selected_keys)

    def toggle_key(self, key: str) -> None:
        selected = set(self._selected_keys)
        if key in selected:
            selected.remove(key)
        else:
            selected.add(key)
        self._set_selection(selected)

    def select_range_to(self, key: str) -> None:
        keys = self._row_keys()
        if key not in keys:
            return
        anchor = self._anchor_key if self._anchor_key in keys else key
        start = keys.index(anchor)
        end = keys.index(key)
        self._set_selection(set(keys[min(start, end) : max(start, end) + 1]))

    def select_all_visible(self) -> None:
        self._set_selection(set(self._row_keys()))

    def clear_selection(self) -> None:
        self._set_selection(set())

    def retain_selection(self, valid_keys: set[str]) -> None:
        self._set_selection(self._selected_keys & valid_keys)

    def _row_keys(self) -> list[str]:
        keys: list[str] = []
        for row in self.ordered_rows:
            value = row.key.value
            if isinstance(value, str):
                keys.append(value)
        return keys

    def _key_at(self, row_index: int) -> str | None:
        if row_index < 0 or row_index >= self.row_count:
            return None
        value = self.ordered_rows[row_index].key.value
        return value if isinstance(value, str) else None

    def _cursor_key(self) -> str | None:
        return self._key_at(self.cursor_coordinate.row)

    def _set_selection(self, selected: set[str]) -> None:
        previous = self._selected_keys
        if selected == previous:
            return
        self._selected_keys = set(selected)
        self._clear_caches()
        _ = self.refresh()
        _ = self.post_message(
            self.SelectionChanged(self, frozenset(self._selected_keys))
        )

    @override
    def _get_row_style(self, row_index: int, base_style: Style) -> Style:
        style = super()._get_row_style(row_index, base_style)
        key = self._key_at(row_index)
        if key is not None and key in self._selected_keys:
            return style + Style.from_color(
                SELECTED_FOREGROUND,
                SELECTED_BACKGROUND,
            )
        return style

    @on(events.MouseDown)
    def _remember_modifiers(self, event: events.MouseDown) -> None:
        self._mouse_down_shift = event.shift
        self._mouse_down_ctrl = event.ctrl

    @override
    async def _on_click(self, event: events.Click) -> None:
        shift = event.shift or self._mouse_down_shift
        ctrl = event.ctrl or self._mouse_down_ctrl
        self._mouse_down_shift = False
        self._mouse_down_ctrl = False

        meta = event.style.meta
        if "row" not in meta or "column" not in meta:
            return

        row_index = cast(int, meta["row"])
        key = self._key_at(row_index)
        if key is None:
            return

        _ = event.prevent_default()
        _ = event.stop()

        if ctrl or shift:
            anchor = self._anchor_key or self._cursor_key()
            _ = self.move_cursor(
                row=row_index,
                column=self.cursor_coordinate.column,
                animate=False,
            )
            if shift:
                self._anchor_key = anchor
                self.select_range_to(key)
            else:
                self._anchor_key = key
                self.toggle_key(key)
            return

        now = time.monotonic()
        double_click = key == self._last_click_key and now - self._last_click_at <= 0.45
        self._last_click_key = None if double_click else key
        self._last_click_at = now
        self._set_selection({key})
        self._anchor_key = key
        _ = self.move_cursor(
            row=row_index,
            column=self.cursor_coordinate.column,
            animate=False,
        )
        if double_click:
            self.action_select_cursor()

    def action_toggle_cursor_selection(self) -> None:
        key = self._cursor_key()
        if key is None:
            return
        self._anchor_key = key
        self.toggle_key(key)

    def action_select_all_visible(self) -> None:
        self._anchor_key = self._cursor_key()
        self.select_all_visible()

    def action_extend_selection_up(self) -> None:
        self._extend_selection(-1)

    def action_extend_selection_down(self) -> None:
        self._extend_selection(1)

    def _extend_selection(self, delta: int) -> None:
        if self.row_count == 0:
            return
        anchor = self._anchor_key or self._cursor_key()
        target_row = max(0, min(self.row_count - 1, self.cursor_coordinate.row + delta))
        target_key = self._key_at(target_row)
        if target_key is None:
            return
        _ = self.move_cursor(row=target_row, animate=False)
        self._anchor_key = anchor
        self.select_range_to(target_key)
