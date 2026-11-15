"""Combining individual sprites into one sprite sheet."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from PIL import Image

from .geometry import Rect

MAX_SHEET_PIXELS = 16384 * 16384

ALIGN_CENTER = "center"
ALIGN_BOTTOM = "bottom"
ALIGN_TOP_LEFT = "topleft"

ORDER_ROWS = "row"   # left to right, then down
ORDER_COLS = "col"   # top to bottom, then right

TRANSPARENT = (0, 0, 0, 0)


@dataclass
class PackSettings:
    cols: int = 0        # 0 = automatic
    rows: int = 0        # 0 = automatic
    cell_w: int = 0      # 0 = largest sprite width
    cell_h: int = 0      # 0 = largest sprite height
    padding: int = 0     # gap between cells
    margin: int = 0      # border around the sheet
    align: str = ALIGN_CENTER
    order: str = ORDER_ROWS
    background: tuple[int, int, int, int] = TRANSPARENT


@dataclass
class PackResult:
    image: Image.Image
    cols: int
    rows: int
    cell_w: int
    cell_h: int
    frames: list[dict] = field(default_factory=list)
    cells: list[Rect] = field(default_factory=list)

    @property
    def empty_cells(self) -> int:
        return self.cols * self.rows - len(self.frames)


def resolve_grid(n: int, cols: int, rows: int) -> tuple[int, int]:
    """Fill in whichever of cols/rows is 0 (automatic). Both 0 gives a near-square grid."""
    if n <= 0:
        return 0, 0
    if cols <= 0 and rows <= 0:
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
    elif cols <= 0:
        cols = math.ceil(n / rows)
    elif rows <= 0:
        rows = math.ceil(n / cols)
    return cols, rows


def _align_offset(align: str, cell_w: int, cell_h: int, w: int, h: int) -> tuple[int, int]:
    if align == ALIGN_TOP_LEFT:
        return 0, 0
    if align == ALIGN_BOTTOM:
        return (cell_w - w) // 2, cell_h - h
    return (cell_w - w) // 2, (cell_h - h) // 2


def pack_sprites(images: list[Image.Image], names: list[str], s: PackSettings) -> PackResult:
    """Lay sprites out on a uniform grid. Raises ValueError for impossible layouts."""
    n = len(images)
    if n == 0:
        raise ValueError("Add some sprites first.")
    cols, rows = resolve_grid(n, s.cols, s.rows)
    if cols * rows < n:
        raise ValueError(f"{cols} x {rows} = {cols * rows} cells, but there are {n} sprites.")

    cw = s.cell_w or max(im.width for im in images)
    ch = s.cell_h or max(im.height for im in images)
    pad, margin = max(0, s.padding), max(0, s.margin)
    sheet_w = margin * 2 + cols * cw + (cols - 1) * pad
    sheet_h = margin * 2 + rows * ch + (rows - 1) * pad
    if sheet_w * sheet_h > MAX_SHEET_PIXELS:
        raise ValueError(f"The sheet would be {sheet_w} x {sheet_h} px, which is too large.")

    def cell_origin(r: int, c: int) -> tuple[int, int]:
        return margin + c * (cw + pad), margin + r * (ch + pad)

    sheet = Image.new("RGBA", (sheet_w, sheet_h), s.background)
    result = PackResult(sheet, cols, rows, cw, ch)
    result.cells = [Rect(*cell_origin(r, c), cw, ch) for r in range(rows) for c in range(cols)]

    for i, im in enumerate(images):
        if s.order == ORDER_COLS:
            c, r = divmod(i, rows)
        else:
            r, c = divmod(i, cols)
        x0, y0 = cell_origin(r, c)
        sprite = im
        if sprite.width > cw or sprite.height > ch:   # explicit cell size smaller than the sprite
            sprite = sprite.crop((0, 0, min(cw, sprite.width), min(ch, sprite.height)))
        dx, dy = _align_offset(s.align, cw, ch, sprite.width, sprite.height)
        sheet.alpha_composite(sprite, (x0 + dx, y0 + dy))
        result.frames.append({
            "name": names[i] if i < len(names) else f"sprite_{i}",
            "index": i, "row": r, "col": c,
            "x": x0, "y": y0, "w": cw, "h": ch,
            "spriteX": x0 + dx, "spriteY": y0 + dy,
            "spriteW": sprite.width, "spriteH": sprite.height,
        })
    return result


def pack_metadata(result: PackResult, image_name: str, s: PackSettings) -> dict:
    """JSON-ready description of a packed sheet."""
    return {
        "image": image_name,
        "width": result.image.width, "height": result.image.height,
        "cols": result.cols, "rows": result.rows,
        "cellW": result.cell_w, "cellH": result.cell_h,
        "padding": s.padding, "margin": s.margin,
        "frames": result.frames,
    }
