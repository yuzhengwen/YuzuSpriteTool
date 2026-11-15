"""Smoke test: runs the core checks, then drives the real UI offscreen and saves screenshots.

Run from the project folder:  .venv\\Scripts\\python.exe tests\\smoke_test.py
Screenshots land in tests/out/. build.bat runs this before every build.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tests", "out")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

import test_core  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from sprite_tool.ui.main_window import MainWindow  # noqa: E402
from sprite_tool.ui.theme import apply_theme  # noqa: E402
from sprite_tool.ui.widgets import PreviewDialog  # noqa: E402


def pump(app: QApplication, n: int = 20) -> None:
    for _ in range(n):
        app.processEvents()


def check_unpack(app, w, sheet_path) -> None:
    u = w.unpack
    w.tabs.setCurrentWidget(u)
    f = u.form
    f.offset_x.setValue(4)
    f.offset_y.setValue(4)
    f.gap_x.setValue(2)
    f.gap_y.setValue(2)
    u.load_sheet(sheet_path)
    pump(app)
    assert u.list.count() == 21, u.list.count()

    # Form changes reach the tab (signal chain form.changed -> debounced reslice).
    f.cell_w.setValue(33)
    assert u._reslice_timer.isActive(), "changing a setting did not schedule a reslice"
    f.cell_w.setValue(32)
    u.reslice()

    u.list.item(2).setSelected(True)
    u.list.item(8).setSelected(True)
    u._on_sheet_clicked(4 + 34 * 3 + 5, 4 + 5, Qt.ControlModifier)   # ctrl-click cell 3 on the sheet
    assert u.selected_rows() == [2, 3, 8], u.selected_rows()
    assert u.name_for(3) == "sample_sheet_03"
    pump(app)
    w.grab().save(os.path.join(OUT, "shot_unpack.png"))


def check_pack(app, w) -> None:
    u, p = w.unpack, w.pack
    u._send_to_pack()   # sends the 3 selected sprites
    assert w.tabs.currentWidget() is p
    p.list.item(0).setSelected(True)
    p.move_selected(1)
    assert [e.name for e in p.ordered_entries()] == ["sample_sheet_03", "sample_sheet_02", "sample_sheet_08"]
    p.repack()
    assert p.result is not None and len(p.result.frames) == 3

    p.form.cols.setValue(2)
    assert p._repack_timer.isActive(), "changing a layout setting did not schedule a repack"
    p.repack()
    assert (p.result.cols, p.result.rows) == (2, 2)

    p.list.clear()
    p._entries.clear()
    u.list.clearSelection()
    u._send_to_pack()   # nothing selected -> sends all
    p.form.cols.setValue(7)
    p.form.gap.setValue(2)
    p.repack()
    assert len(p.result.frames) == 21
    pump(app, 30)
    w.grab().save(os.path.join(OUT, "shot_pack.png"))


def check_tab_bar(w) -> None:
    """Regression: no light pixels may show around the tabs (the old white base line)."""
    img = w.grab().toImage()
    bar = w.tabs.tabBar()
    bottom = bar.mapTo(w, bar.rect().bottomLeft()).y()
    worst = 0
    for y in range(0, bottom + 2):
        for x in range(0, img.width(), 2):
            c = img.pixelColor(x, y)
            if c.red() > 200 and c.green() > 200 and c.blue() > 200:   # near-white
                worst += 1
    assert worst == 0, f"{worst} near-white pixels in the tab bar area"


def check_preview(app, w) -> None:
    u = w.unpack
    dlg = PreviewDialog(w, u.sprites[0].image, u.name_for(0), lambda: None)
    dlg.show()
    pump(app, 10)
    dlg.grab().save(os.path.join(OUT, "shot_preview.png"))
    dlg.close()


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    test_core.run_all()
    sheet_path = os.path.join(OUT, "sample_sheet.png")
    test_core.make_sample_sheet().save(sheet_path)

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    w = MainWindow()
    w.resize(1360, 860)
    w.show()
    pump(app)

    check_unpack(app, w, sheet_path)
    check_tab_bar(w)
    check_pack(app, w)
    check_preview(app, w)
    w.close()
    print("ui OK")


if __name__ == "__main__":
    main()
