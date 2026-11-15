"""Small persisted preferences (last folder, window geometry, open tab)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings

from .. import ORG_NAME, SETTINGS_NAME

_KEY_LAST_DIR = "lastDir"
_KEY_GEOMETRY = "geometry"
_KEY_TAB = "tab"


def _store() -> QSettings:
    return QSettings(ORG_NAME, SETTINGS_NAME)


def last_dir() -> str:
    return str(_store().value(_KEY_LAST_DIR, str(Path.home())))


def remember_dir(path: str | Path) -> None:
    """Remember a folder, or the folder containing a file."""
    p = Path(path)
    _store().setValue(_KEY_LAST_DIR, str(p if p.is_dir() else p.parent))


def window_geometry() -> QByteArray | None:
    return _store().value(_KEY_GEOMETRY)


def save_window_geometry(geometry: QByteArray) -> None:
    _store().setValue(_KEY_GEOMETRY, geometry)


def last_tab() -> int:
    try:
        return int(_store().value(_KEY_TAB, 0))
    except (TypeError, ValueError):
        return 0


def save_last_tab(index: int) -> None:
    _store().setValue(_KEY_TAB, index)
