import json
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir


def get_data_dir() -> Path:
    """returns the application's data directory, ensuring it exists"""
    data_dir = Path(user_data_dir("csvcatalog", "tomashevich"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_config_path() -> Path:
    """returns the path to the settings.json file"""
    return get_data_dir() / "settings.json"


def load_config() -> dict[str, Any]:
    """loads the settings from settings.json, returning an empty dict if it doesnt exist"""
    config_path = get_config_path()
    if not config_path.exists():
        return {}
    with config_path.open("r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_config(config: dict[str, Any]) -> None:
    """saves the given dictionary to settings.json"""
    config_path = get_config_path()
    with config_path.open("w") as f:
        json.dump(config, f, indent=4)
