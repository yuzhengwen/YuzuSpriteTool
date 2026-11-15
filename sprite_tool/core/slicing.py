"""Cutting a sprite sheet into individual sprites."""
from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image

from .geometry import Rect

MAX_CELLS = 10_000

MODE_SIZE = "size"   # fixed cell width/height
MODE_GRID = "grid"   # fixed number of columns/rows

CORNERS = ("tl", "tr", "bl", "br")


@dataclass
class SliceSettings:
    mode: str = MODE_SIZE
    cell_w: int = 32
    cell_h: int = 32
    cols: int = 4
    rows: int = 4
    offset_x: int = 0
    offset_y: int = 0
    spacing_x: int = 0
    spacing_y: int = 0
    corner: str = "tl"              # where cutting starts: tl, tr, bl, br
    include_partial: bool = False   # keep cut-off cells at the far edges (size mode)
    skip_empty: bool = True
    trim: bool = False


@dataclass
class Sprite:
    image: Image.Image
    cell: Rect          # where the cell sits on the sheet
    trim_x: int = 0     # offset of the trimmed image inside its cell
    trim_y: int = 0


def _grid_shape(avail_w: int, avail_h: int, s: SliceSettings) -> tuple[int, int, int, int] | None:
    """Return (cols, rows, cell_w, cell_h), or None if nothing fits."""
    sx, sy = max(0, s.spacing_x), max(0, s.spacing_y)
    if s.mode == MODE_GRID:
        cols, rows = max(1, s.cols), max(1, s.rows)
        cw = (avail_w - (cols - 1) * sx) // cols
        ch = (avail_h - (rows - 1) * sy) // rows
        if cw <= 0 or ch <= 0:
            return None
        return cols, rows, cw, ch

    cw, ch = max(1, s.cell_w), max(1, s.cell_h)
    if s.include_partial:
        cols = max(1, math.ceil((avail_w + sx) / (cw + sx)))
        rows = max(1, math.ceil((avail_h + sy) / (ch + sy)))
    else:
        cols = (avail_w + sx) // (cw + sx)
        rows = (avail_h + sy) // (ch + sy)
    return cols, rows, cw, ch


def compute_cells(img_w: int, img_h: int, s: SliceSettings) -> list[Rect]:
    """Cells in reading order, starting at the chosen corner plus the offset.

    Raises ValueError if the settings would produce an unreasonable number of cells.
    """
    ox, oy = max(0, s.offset_x), max(0, s.offset_y)
    sx, sy = max(0, s.spacing_x), max(0, s.spacing_y)
    avail_w, avail_h = img_w - ox, img_h - oy
    if avail_w <= 0 or avail_h <= 0:
        return []

    shape = _grid_shape(avail_w, avail_h, s)
    if shape is None:
        return []
    cols, rows, cw, ch = shape
    if cols * rows > MAX_CELLS:
        raise ValueError(f"That would make {cols * rows:,} cells (limit {MAX_CELLS:,}). Use a bigger cell size.")

    flip_x = s.corner in ("tr", "br")
    flip_y = s.corner in ("bl", "br")
    cells: list[Rect] = []
    for r in range(rows):
        for c in range(cols):
            # Position measured from the start corner, then mirrored into sheet space.
            x = ox + c * (cw + sx)
            y = oy + r * (ch + sy)
            w = min(cw, img_w - x)
            h = min(ch, img_h - y)
            if w <= 0 or h <= 0:
                continue
            if flip_x:
                x = img_w - x - w
            if flip_y:
                y = img_h - y - h
            cells.append(Rect(x, y, w, h))
    return cells


def slice_sheet(img: Image.Image, s: SliceSettings) -> tuple[list[Rect], list[Sprite]]:
    """Return every cell, plus the sprites kept after skipping/trimming."""
    cells = compute_cells(img.width, img.height, s)
    sprites: list[Sprite] = []
    for cell in cells:
        crop = img.crop((cell.x, cell.y, cell.x + cell.w, cell.y + cell.h))
        bbox = crop.getchannel("A").getbbox()
        if bbox is None and s.skip_empty:
            continue
        tx = ty = 0
        if s.trim and bbox is not None:
            crop = crop.crop(bbox)
            tx, ty = bbox[0], bbox[1]
        sprites.append(Sprite(crop, cell, tx, ty))
    return cells, sprites
