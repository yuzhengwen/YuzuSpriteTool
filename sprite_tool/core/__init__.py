"""Image processing (Pillow only, no UI). Safe to use from scripts and tests."""
from .geometry import Rect
from .image_io import IMAGE_EXTS, is_fully_transparent, is_image_file, load_rgba
from .naming import DEFAULT_PREFIX, natural_key, numbered_name
from .packing import (
    ALIGN_BOTTOM, ALIGN_CENTER, ALIGN_TOP_LEFT, ORDER_COLS, ORDER_ROWS,
    PackResult, PackSettings, pack_metadata, pack_sprites, resolve_grid,
)
from .slicing import MODE_GRID, MODE_SIZE, SliceSettings, Sprite, compute_cells, slice_sheet

__all__ = [
    "Rect", "IMAGE_EXTS", "is_fully_transparent", "is_image_file", "load_rgba",
    "DEFAULT_PREFIX", "natural_key", "numbered_name",
    "ALIGN_BOTTOM", "ALIGN_CENTER", "ALIGN_TOP_LEFT", "ORDER_COLS", "ORDER_ROWS",
    "PackResult", "PackSettings", "pack_metadata", "pack_sprites", "resolve_grid",
    "MODE_GRID", "MODE_SIZE", "SliceSettings", "Sprite", "compute_cells", "slice_sheet",
]
