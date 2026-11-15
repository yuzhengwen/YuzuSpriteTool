"""Image processing for Yuzu Sprite Tool (no UI code here).

Slicing a sheet into sprites and packing sprites into a sheet, using Pillow.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from PIL import Image

MAX_CELLS = 10_000
MAX_SHEET_PIXELS = 16384 * 16384


def load_rgba(path: str) -> Image.Image:
    with Image.open(path) as im:
        im.load()
        return im.convert("RGBA")


def is_empty(img: Image.Image) -> bool:
    return img.getchannel("A").getbbox() is None


# ------------------------------------------------------------------ slicing

@dataclass
class SliceSettings:
    mode: str = "size"            # "size" (fixed cell w/h) or "grid" (cols x rows)
    cell_w: int = 32
    cell_h: int = 32
    cols: int = 4
    rows: int = 4
    offset_x: int = 0
    offset_y: int = 0
    spacing_x: int = 0
    spacing_y: int = 0
    corner: str = "tl"            # start corner: tl, tr, bl, br
    include_partial: bool = False  # keep cut-off cells at the right/bottom edge (size mode)
    skip_empty: bool = True
    trim: bool = False


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass
class Sprite:
    image: Image.Image
    cell: Rect                    # where the cell sits on the sheet
    trim_x: int = 0               # offset of the trimmed image inside the cell
    trim_y: int = 0


def compute_cells(img_w: int, img_h: int, s: SliceSettings) -> list[Rect]:
    """Cells in reading order, starting at the chosen corner (+ offset)."""
    ox, oy = max(0, s.offset_x), max(0, s.offset_y)
    sx, sy = max(0, s.spacing_x), max(0, s.spacing_y)
    avail_w, avail_h = img_w - ox, img_h - oy
    if avail_w <= 0 or avail_h <= 0:
        return []

    if s.mode == "grid":
        cols, rows = max(1, s.cols), max(1, s.rows)
        cw = (avail_w - (cols - 1) * sx) // cols
        ch = (avail_h - (rows - 1) * sy) // rows
        if cw <= 0 or ch <= 0:
            return []
    else:
        cw, ch = max(1, s.cell_w), max(1, s.cell_h)
        if s.include_partial:
            cols = max(1, math.ceil((avail_w + sx) / (cw + sx)))
            rows = max(1, math.ceil((avail_h + sy) / (ch + sy)))
        else:
            cols = (avail_w + sx) // (cw + sx)
            rows = (avail_h + sy) // (ch + sy)

    if cols * rows > MAX_CELLS:
        raise ValueError(f"That would make {cols * rows:,} cells (limit {MAX_CELLS:,}). Use a bigger cell size.")

    flip_x = s.corner in ("tr", "br")
    flip_y = s.corner in ("bl", "br")
    cells: list[Rect] = []
    for r in range(rows):
        for c in range(cols):
            # Position measured from the start corner.
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


# ------------------------------------------------------------------ packing

@dataclass
class PackSettings:
    cols: int = 0                 # 0 = automatic
    rows: int = 0                 # 0 = automatic
    cell_w: int = 0               # 0 = largest sprite width
    cell_h: int = 0               # 0 = largest sprite height
    padding: int = 0              # gap between cells
    margin: int = 0               # border around the sheet
    align: str = "center"         # center, topleft, bottom
    order: str = "row"            # row (left->right, then down) or col (top->bottom, then right)
    background: tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass
class PackResult:
    image: Image.Image
    cols: int
    rows: int
    cell_w: int
    cell_h: int
    frames: list[dict] = field(default_factory=list)
    cells: list[Rect] = field(default_factory=list)


def resolve_grid(n: int, cols: int, rows: int) -> tuple[int, int]:
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


def pack_sprites(images: list[Image.Image], names: list[str], s: PackSettings) -> PackResult:
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

    sheet = Image.new("RGBA", (sheet_w, sheet_h), s.background)
    result = PackResult(sheet, cols, rows, cw, ch)
    for r in range(rows):
        for c in range(cols):
            result.cells.append(Rect(margin + c * (cw + pad), margin + r * (ch + pad), cw, ch))

    for i, im in enumerate(images):
        if s.order == "col":
            c, r = divmod(i, rows)
        else:
            r, c = divmod(i, cols)
        x0 = margin + c * (cw + pad)
        y0 = margin + r * (ch + pad)
        sprite = im
        if sprite.width > cw or sprite.height > ch:
            sprite = sprite.crop((0, 0, min(cw, sprite.width), min(ch, sprite.height)))
        if s.align == "topleft":
            dx, dy = 0, 0
        elif s.align == "bottom":
            dx, dy = (cw - sprite.width) // 2, ch - sprite.height
        else:
            dx, dy = (cw - sprite.width) // 2, (ch - sprite.height) // 2
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
    return {
        "image": image_name,
        "width": result.image.width, "height": result.image.height,
        "cols": result.cols, "rows": result.rows,
        "cellW": result.cell_w, "cellH": result.cell_h,
        "padding": s.padding, "margin": s.margin,
        "frames": result.frames,
    }
