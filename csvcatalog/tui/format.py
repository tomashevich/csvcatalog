from datetime import datetime
from pathlib import Path

_SIZE_UNITS = ("B", "KiB", "MiB", "GiB", "TiB")


def human_size(size: int) -> str:
    """format a byte count for the summary line"""
    value = float(size)
    for unit in _SIZE_UNITS:
        if value < 1024 or unit == _SIZE_UNITS[-1]:
            precision = 0 if unit == "B" else 1
            return f"{value:.{precision}f} {unit}"
        value /= 1024
    return f"{size} B"


def truncate(text: str, width: int) -> str:
    """shorten text to a display width, adding an ellipsis when needed"""
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return "…"
    return f"{text[: width - 1]}…"


def database_size(path: Path) -> int:
    """return the size of the database file including its wal/shm companions"""
    total = 0
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{path}{suffix}")
        try:
            total += candidate.stat().st_size
        except FileNotFoundError:
            continue
    return total


def merge_date(created_at: str, date_str: str) -> str:
    """replace the date part of an iso timestamp while keeping its time and tz"""
    new_date = datetime.strptime(date_str, "%Y-%m-%d")
    try:
        original = datetime.fromisoformat(created_at)
    except ValueError:
        return new_date.isoformat()
    return new_date.replace(
        hour=original.hour,
        minute=original.minute,
        second=original.second,
        microsecond=original.microsecond,
        tzinfo=original.tzinfo,
    ).isoformat()
