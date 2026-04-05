"""Configuration management for the audiobook app."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any


@dataclass
class AppConfig:
    """User configuration."""
    voice: str = "af_heart"
    speed: float = 1.0
    volume: float = 1.0
    custom_voices: list[str] = field(default_factory=list)
    view_mode: str = "text"
    auto_pdf_sync: bool = True
    back_cache_size: int = 10
    lookahead_size: int = 1
    last_opened_pdf: str = ""
    window_geometry: str = ""
    theme: str = "catppuccin_mocha"
    auto_resume: bool = True


def _get_config_path() -> Path:
    """Get platform-appropriate config directory."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif os.name == "posix" and os.path.exists("/Applications"):
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"

    config_dir = base / "pdf-audiobook"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


def load_config() -> AppConfig:
    """Load configuration from file, or return defaults."""
    config_path = _get_config_path()
    if not config_path.exists():
        return AppConfig()

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return AppConfig(**data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return AppConfig()


def save_config(config: AppConfig) -> None:
    """Save configuration to file."""
    config_path = _get_config_path()
    config_path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
