import json
from pathlib import Path

from platformdirs import user_data_dir
from pydantic import BaseModel, ValidationError


class Settings(BaseModel):
    """defines the application settings model"""

    db_path: Path | None = None
    encryption: bool = False
    filters: dict[str, str] = {}


def get_data_dir() -> Path:
    """returns the application's data directory, ensuring it exists"""
    data_dir = Path(user_data_dir("csvcatalog", "tomashevich"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_config_path() -> Path:
    """returns the path to the settings.json file"""
    return get_data_dir() / "settings.json"


def load_config() -> Settings:
    """loads the settings from settings.json, returning default settings if it doesnt exist or is invalid"""
    config_path = get_config_path()
    if not config_path.exists():
        return Settings()

    with config_path.open("r") as f:
        try:
            data = json.load(f)
            return Settings(**data)
        except (json.JSONDecodeError, ValidationError):
            return Settings()


def save_config(settings: Settings) -> None:
    """saves the given settings model to settings.json"""
    config_path = get_config_path()
    with config_path.open("w") as f:
        f.write(settings.model_dump_json(indent=4))
