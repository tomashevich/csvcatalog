from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import final, override

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option

DB_SUFFIXES = frozenset({".db", ".sqlite", ".sqlite3"})


@dataclass(frozen=True)
class PathSuggestion:
    path: Path
    is_dir: bool


def suggest_paths(
    value: str,
    *,
    suffixes: frozenset[str] = DB_SUFFIXES,
    limit: int = 30,
) -> list[PathSuggestion]:
    """suggest directories and database files for a partially typed path"""
    raw = value.strip()
    if not raw:
        base = Path.cwd()
        prefix = ""
    else:
        expanded = Path(raw).expanduser()
        if expanded.is_dir():
            base = expanded
            prefix = ""
        else:
            base = expanded.parent
            prefix = expanded.name
            while not base.is_dir() and base != base.parent:
                base = base.parent

    try:
        entries: Iterable[Path] = sorted(
            base.iterdir(),
            key=lambda path: (not path.is_dir(), path.name.casefold()),
        )
    except OSError:
        return []

    def is_candidate(entry: Path) -> bool:
        return entry.is_dir() or entry.suffix.casefold() in suffixes

    suggestions: list[PathSuggestion] = []
    for entry in entries:
        if not entry.name.startswith(prefix):
            continue
        if entry.name.startswith(".") and not prefix.startswith("."):
            continue
        if is_candidate(entry):
            suggestions.append(PathSuggestion(entry, entry.is_dir()))
        if len(suggestions) >= limit:
            break

    if not suggestions and prefix:
        for entry in entries:
            if entry.name.startswith(".") and not prefix.startswith("."):
                continue
            if is_candidate(entry):
                suggestions.append(PathSuggestion(entry, entry.is_dir()))
            if len(suggestions) >= limit:
                break

    return suggestions


@final
class PathField(Container):
    """path input with filesystem autocompletion and keyboard navigation"""

    def __init__(
        self,
        value: str = "",
        *,
        placeholder: str = "",
        suffixes: frozenset[str] = DB_SUFFIXES,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._value = value
        self._last_value = value
        self._placeholder = placeholder
        self._suffixes = suffixes

    @property
    def value(self) -> str:
        """the currently entered path"""
        return self.query_one("#path-input", Input).value

    def hide_suggestions(self) -> None:
        """hide the filesystem suggestion list"""
        self.query_one("#path-options", OptionList).display = False

    @override
    def compose(self) -> ComposeResult:
        yield Input(
            self._value,
            placeholder=self._placeholder,
            id="path-input",
        )
        yield OptionList(id="path-options", compact=True)

    def on_mount(self) -> None:
        self._last_value = self.value
        self._refresh_suggestions(show=False)
        _ = self.query_one("#path-input", Input).focus()

    @on(Input.Changed, "#path-input")
    def _path_changed(self, event: Input.Changed) -> None:
        if event.value == self._last_value:
            return
        self._last_value = event.value
        self._refresh_suggestions(show=True)

    @on(OptionList.OptionSelected, "#path-options")
    def _option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id is None:
            return
        path = Path(event.option.id)
        input_widget = self.query_one("#path-input", Input)
        if path.is_dir():
            input_widget.value = f"{path}/"
            self._refresh_suggestions(show=True)
        else:
            input_widget.value = str(path)
            self.query_one("#path-options", OptionList).display = False
        _ = input_widget.focus()

    def on_key(self, event: events.Key) -> None:
        input_widget = self.query_one("#path-input", Input)
        options = self.query_one("#path-options", OptionList)
        if event.key == "down" and input_widget.has_focus:
            if not options.display:
                self._refresh_suggestions(show=True)
            if options.display:
                _ = event.prevent_default()
                _ = event.stop()
                _ = options.focus()
                options.action_cursor_down()
            return
        if not options.display:
            return
        if event.key == "escape" and options.has_focus:
            _ = event.prevent_default()
            _ = event.stop()
            _ = input_widget.focus()

    def _refresh_suggestions(self, *, show: bool) -> None:
        options = self.query_one("#path-options", OptionList)
        _ = options.clear_options()
        suggestions = suggest_paths(self.value, suffixes=self._suffixes)
        if not suggestions:
            options.display = False
            return

        option_items: list[Option] = []
        for suggestion in suggestions:
            label = Text(
                f"{suggestion.path.name}/"
                if suggestion.is_dir
                else suggestion.path.name,
                style="bold #67e8f9" if suggestion.is_dir else "#cbd5e1",
            )
            option_items.append(Option(label, id=str(suggestion.path)))
        _ = options.add_options(option_items)
        options.display = show
