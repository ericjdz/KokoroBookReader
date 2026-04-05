"""Bookmark save/restore for audiobook sessions."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class Bookmark:
    """Represents a saved reading position."""
    file_path: str
    chunk_index: int
    total_chunks: int
    timestamp: str  # ISO format
    voice: str = ""
    speed: float = 1.0


def _get_state_dir() -> Path:
    """Get platform-appropriate state directory."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif os.name == "posix" and os.path.exists("/Applications"):
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"

    state_dir = base / "pdf-audiobook"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def save_bookmark(bookmark: Bookmark) -> None:
    """Save bookmark to state file."""
    state_file = _get_state_dir() / "state.json"
    state_file.write_text(json.dumps(asdict(bookmark), indent=2), encoding="utf-8")


def load_bookmark() -> Bookmark | None:
    """Load bookmark from state file, or None if not found."""
    state_file = _get_state_dir() / "state.json"
    if not state_file.exists():
        return None

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return Bookmark(**data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def clear_bookmark() -> None:
    """Remove saved bookmark."""
    state_file = _get_state_dir() / "state.json"
    if state_file.exists():
        state_file.unlink()


def has_bookmark_for_file(file_path: str) -> bool:
    """Check if a bookmark exists for the given file."""
    bookmark = load_bookmark()
    if bookmark is None:
        return False
    return os.path.abspath(bookmark.file_path) == os.path.abspath(file_path)
