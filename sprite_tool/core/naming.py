"""File naming and sorting helpers."""
from __future__ import annotations

import re

DEFAULT_PREFIX = "sprite"


def numbered_name(prefix: str, index: int, total: int) -> str:
    """`prefix_07`: zero-padded so files sort correctly (at least 2 digits)."""
    prefix = prefix.strip() or DEFAULT_PREFIX
    digits = max(2, len(str(max(0, total - 1))))
    return f"{prefix}_{index:0{digits}d}"


def natural_key(text: str) -> list:
    """Sort key where `walk_2` comes before `walk_10`."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]
