"""Checks for the pure image logic in sprite_tool.core (no Qt needed).

Run:  .venv\\Scripts\\python.exe tests\\test_core.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw  # noqa: E402

from sprite_tool import core  # noqa: E402

# Sample sheet: 6 x 4 cells of 32 px, 2 px gaps, 4 px offset; the last 3 cells are empty.
CELL, GAP, OFFSET, COLS, ROWS, FILLED = 32, 2, 4, 6, 4, 21
COLORS = [(255, 90, 90), (90, 200, 120), (90, 140, 255), (255, 200, 60), (200, 100, 255), (60, 220, 220)]


def make_sample_sheet() -> Image.Image:
    w = OFFSET + COLS * CELL + (COLS - 1) * GAP
    h = OFFSET + ROWS * CELL + (ROWS - 1) * GAP
    sheet = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for i in range(FILLED):
        r, c = divmod(i, COLS)
        x, y = OFFSET + c * (CELL + GAP), OFFSET + r * (CELL + GAP)
        d.ellipse((x + 4, y + 4 + (i % 3), x + 27, y + 27), fill=COLORS[i % 6] + (255,), outline=(20, 20, 20, 255))
        d.text((x + 11, y + 10), str(i), fill=(0, 0, 0, 255))
    return sheet


def size_settings(**kw) -> core.SliceSettings:
    base = dict(mode=core.MODE_SIZE, cell_w=CELL, cell_h=CELL, offset_x=OFFSET, offset_y=OFFSET,
                spacing_x=GAP, spacing_y=GAP)
    base.update(kw)
    return core.SliceSettings(**base)


def test_slice_by_size(sheet):
    cells, sprites = core.slice_sheet(sheet, size_settings())
    assert len(cells) == COLS * ROWS and len(sprites) == FILLED, (len(cells), len(sprites))
    assert cells[7] == core.Rect(OFFSET + CELL + GAP, OFFSET + CELL + GAP, CELL, CELL)


def test_slice_by_grid(sheet):
    cells, sprites = core.slice_sheet(sheet, size_settings(mode=core.MODE_GRID, cols=COLS, rows=ROWS))
    assert len(cells) == COLS * ROWS and cells[0].w == CELL and len(sprites) == FILLED


def test_start_corner(sheet):
    cells, _ = core.slice_sheet(sheet, size_settings(corner="br", offset_x=0, offset_y=0))
    first = cells[0]
    assert first.x + first.w == sheet.width and first.y + first.h == sheet.height


def test_keep_empty_and_trim(sheet):
    _, kept = core.slice_sheet(sheet, size_settings(skip_empty=False))
    assert len(kept) == COLS * ROWS
    _, trimmed = core.slice_sheet(sheet, size_settings(trim=True))
    assert trimmed[0].image.width < CELL and trimmed[0].trim_x > 0


def test_too_many_cells(sheet):
    try:
        core.compute_cells(100_000, 100_000, core.SliceSettings(cell_w=1, cell_h=1))
    except ValueError:
        return
    raise AssertionError("expected ValueError for a huge cell count")


def test_pack(sheet):
    _, sprites = core.slice_sheet(sheet, size_settings())
    images = [s.image for s in sprites]
    r = core.pack_sprites(images, [f"s{i}" for i in range(len(images))],
                          core.PackSettings(cols=7, padding=1, margin=2))
    assert (r.cols, r.rows) == (7, 3)
    assert r.image.size == (2 * 2 + 7 * CELL + 6, 2 * 2 + 3 * CELL + 2)
    assert r.empty_cells == 0 and len(r.cells) == 21

    col_major = core.pack_sprites(images[:4], [], core.PackSettings(cols=2, order=core.ORDER_COLS))
    assert [(f["row"], f["col"]) for f in col_major.frames] == [(0, 0), (1, 0), (0, 1), (1, 1)]

    try:
        core.pack_sprites(images, [], core.PackSettings(cols=2, rows=2))
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError when cells < sprites")


def test_resolve_grid_and_naming():
    assert core.resolve_grid(10, 0, 0) == (4, 3)
    assert core.resolve_grid(10, 0, 2) == (5, 2)
    assert core.numbered_name("walk", 3, 12) == "walk_03"
    assert core.numbered_name("  ", 3, 1000) == "sprite_003"
    assert sorted(["a10", "a2", "A1"], key=core.natural_key) == ["A1", "a2", "a10"]


def run_all() -> None:
    sheet = make_sample_sheet()
    tests = [test_slice_by_size, test_slice_by_grid, test_start_corner, test_keep_empty_and_trim,
             test_too_many_cells, test_pack]
    for t in tests:
        t(sheet)
    test_resolve_grid_and_naming()
    print(f"core OK ({len(tests) + 1} tests)")


if __name__ == "__main__":
    run_all()
