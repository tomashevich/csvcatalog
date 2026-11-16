from typing import final, override

from textual import events
from textual.app import ComposeResult
from textual.containers import Container, HorizontalScroll
from textual.message import Message
from textual.widgets import Static


@final
class EditorTab(Static):
    """single code-editor style tab with an optional close cross"""

    class Activated(Message):
        tab_id: str

        def __init__(self, tab_id: str) -> None:
            self.tab_id = tab_id
            super().__init__()

    class CloseRequested(Message):
        tab_id: str

        def __init__(self, tab_id: str) -> None:
            self.tab_id = tab_id
            super().__init__()

    def __init__(self, tab_id: str, title: str, *, closable: bool) -> None:
        super().__init__(classes="editor-tab")
        self.tab_id = tab_id
        self._title = title
        self._closable = closable
        if closable:
            _ = self.add_class("closable")
        self._refresh_label()

    def _refresh_label(self) -> None:
        suffix = "  ×" if self._closable else " "
        self.update(f" {self._title}{suffix}")

    def set_active(self, active: bool) -> None:
        _ = self.set_class(active, "-active")

    def on_click(self, event: events.Click) -> None:
        if self._closable and event.x >= self.size.width - 3:
            _ = event.stop()
            _ = self.post_message(self.CloseRequested(self.tab_id))
            return
        _ = event.stop()
        _ = self.post_message(self.Activated(self.tab_id))


@final
class EditorTabs(Container):
    """horizontally scrollable strip of editor tabs"""

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._tabs: dict[str, EditorTab] = {}
        self._active_id = ""

    @override
    def compose(self) -> ComposeResult:
        yield HorizontalScroll(id="tab-strip")

    @property
    def active_id(self) -> str:
        return self._active_id

    def add_tab(self, tab_id: str, title: str, *, closable: bool = True) -> None:
        if tab_id in self._tabs:
            return
        tab = EditorTab(tab_id, title, closable=closable)
        if tab_id == self._active_id:
            tab.set_active(True)
        self._tabs[tab_id] = tab
        _ = self.query_one("#tab-strip", HorizontalScroll).mount(tab)

    def remove_tab(self, tab_id: str) -> None:
        tab = self._tabs.pop(tab_id, None)
        if tab is not None:
            _ = tab.remove()

    def set_active(self, tab_id: str) -> None:
        self._active_id = tab_id
        for current_id, tab in self._tabs.items():
            tab.set_active(current_id == tab_id)
            if current_id == tab_id:
                tab.scroll_visible()
