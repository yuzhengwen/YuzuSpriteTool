"""Finding bundled files, both from source and inside the PyInstaller exe."""
from __future__ import annotations

import sys
from pathlib import Path

# From source: the project root (the folder containing sprite_tool/).
# Frozen: PyInstaller's unpack folder, where `datas` from the .spec end up.
_BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))

ICON_PATH = _BASE / "assets" / "icon.ico"


def resource_path(relative: str) -> Path:
    return _BASE / relative
