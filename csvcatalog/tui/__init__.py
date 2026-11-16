from collections.abc import Callable
from pathlib import Path

from ..config import Settings
from ..storage import BaseStorage
from .app import CatalogTUI


def run_tui(
    storage: BaseStorage | None,
    settings: Settings,
    db_path: Path,
    *,
    db_error: str | None = None,
    on_storage_change: Callable[[BaseStorage | None], None] | None = None,
) -> None:
    """start the interactive terminal catalog browser"""
    _ = CatalogTUI(
        storage,
        settings,
        db_path,
        db_error=db_error,
        on_storage_change=on_storage_change,
    ).run()
