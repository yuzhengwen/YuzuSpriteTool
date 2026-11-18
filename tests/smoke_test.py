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
from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from sprite_tool.ui.main_window import MainWindow  # noqa: E402
from sprite_tool.ui.theme import apply_theme  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from sprite_tool.core import Rect, SpriteEdit  # noqa: E402
from sprite_tool.ui.dialogs import PreviewDialog, SpriteEditorDialog  # noqa: E402
from sprite_tool.ui.widgets.pack_entry_delegate import PackEntryDelegate  # noqa: E402


def pump(app: QApplication, n: int = 20) -> None:
    for _ in range(n):
        app.processEvents()


def check_unpack(app, w, sheet_path) -> None:
    u = w.unpack
    w.tabs.setCurrentWidget(u)
    f = u.slicer.form
    f.offset_x.setValue(4)
    f.offset_y.setValue(4)
    f.gap_x.setValue(2)
    f.gap_y.setValue(2)
    u.load_sheet(sheet_path)
    pump(app)
    assert u.list.count() == 21, u.list.count()

    # Form changes reach the tab (signal chain form.changed -> debounced reslice).
    f.cell_w.setValue(33)
    assert u.slicer._reslice_timer.isActive(), "changing a setting did not schedule a reslice"
    f.cell_w.setValue(32)
    u.slicer.reslice()

    u.list.item(2).setSelected(True)
    u.list.item(8).setSelected(True)
    u.slicer._on_view_clicked(4 + 34 * 3 + 5, 4 + 5, Qt.ControlModifier)   # ctrl-click cell 3 on the sheet
    assert u.selected_rows() == [2, 3, 8], u.selected_rows()
    assert u.name_for(3) == "sample_sheet_03"
    pump(app)
    w.grab().save(os.path.join(OUT, "shot_unpack.png"))


def check_pack(app, w) -> None:
    u, p = w.unpack, w.pack
    u._send_to_pack()   # sends the 3 selected sprites
    assert w.tabs.currentWidget() is p
    p.sprites.list.item(0).setSelected(True)
    p.sprites.move_selected(1)
    assert [e.name for e in p.sprites.entries()] == ["sample_sheet_03", "sample_sheet_02", "sample_sheet_08"]
    p.repack()
    assert p.result is not None and len(p.result.frames) == 3

    p.form.cols.setValue(2)
    assert p._repack_timer.isActive(), "changing a layout setting did not schedule a repack"
    p.repack()
    assert (p.result.cols, p.result.rows) == (2, 2)

    p.sprites.clear(confirm=False)
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


def check_sprite_editor(app, w) -> None:
    """Crop/resize in the editor, then the list's Edit, thumbnail and ✕ buttons."""
    p = w.pack
    entry = p.sprites.entry_at(0)
    original_size = entry.original.size   # 32 x 32

    # 1) The dialog itself: crop to 20x10 at (4,6), then scale 300 %.
    dlg = SpriteEditorDialog(w, entry.original, entry.name)
    dlg.show()
    pump(app, 10)
    # Regression: sprites with transparent edges must fit fully (fitInView used to fit the opaque shape).
    view = dlg.crop_view
    on_screen = view.mapFromScene(view._pix_item.sceneBoundingRect()).boundingRect()
    assert view.viewport().rect().contains(on_screen), (on_screen, view.viewport().rect())
    dlg.crop_view.cropDrawn.emit(Rect(4, 6, 20, 10))     # same as dragging on the image
    assert dlg.crop_form.isChecked() and dlg.crop_form.crop_rect() == Rect(4, 6, 20, 10)
    assert dlg.resize_form.width_box.value() == 20       # resize mirrors the crop while off
    dlg.resize_form.setChecked(True)
    dlg.resize_form.scale_box.setValue(300)
    assert dlg.resize_form.target_size() == (60, 30), dlg.resize_form.target_size()
    dlg.resize_form.width_box.setValue(40)                # keep-aspect: height follows
    assert dlg.resize_form.target_size() == (40, 20)
    dlg._update_preview()
    pump(app, 10)
    dlg.grab().save(os.path.join(OUT, "shot_editor.png"))
    edit = dlg.current_edit()
    assert edit == SpriteEdit(Rect(4, 6, 20, 10), (40, 20), "nearest"), edit
    dlg._reset()
    assert dlg.current_edit() is None
    dlg.close()

    # 2) Clicking Edit on a row opens the editor; Apply stores the edit (exec stubbed: non-blocking).
    opened = []

    def fake_exec(self):
        opened.append(self)
        self.edit = edit
        return SpriteEditorDialog.Accepted

    real_exec = SpriteEditorDialog.exec
    SpriteEditorDialog.exec = fake_exec
    try:
        rect = p.sprites.list.visualItemRect(p.sprites.list.item(0))
        QTest.mouseClick(p.sprites.list.viewport(), Qt.LeftButton, Qt.NoModifier, PackEntryDelegate._edit_rect(rect).center())
        pump(app)
        assert len(opened) == 1, "Edit button did not open the editor"
        assert entry.is_edited and entry.image.size == (40, 20) and entry.original.size == original_size
        assert p.sprites.list.item(0).data(Qt.UserRole + 2) is True
        assert "edited" in p.sprites.list.item(0).text()

        # Thumbnail click opens it too.
        thumb = p.sprites.list.visualItemRect(p.sprites.list.item(1))
        QTest.mouseClick(p.sprites.list.viewport(), Qt.LeftButton, Qt.NoModifier, thumb.topLeft() + QPoint(30, thumb.height() // 2))
        pump(app)
        assert len(opened) == 2, "thumbnail click did not open the editor"
    finally:
        SpriteEditorDialog.exec = real_exec

    p.repack()
    assert p.result.frames[0]["spriteW"] == 40
    pump(app, 20)
    w.grab().save(os.path.join(OUT, "shot_pack_edited.png"))

    # 3) ✕ reverts to the original image.
    rect = p.sprites.list.visualItemRect(p.sprites.list.item(0))
    QTest.mouseClick(p.sprites.list.viewport(), Qt.LeftButton, Qt.NoModifier, PackEntryDelegate._revert_rect(rect).center())
    pump(app)
    assert not entry.is_edited and entry.image is entry.original, "✕ did not revert"
    p.sprites.entry_at(1).set_edit(None)
    p.sprites._sync_item(p.sprites.list.item(1), p.sprites.entry_at(1))


def check_animate(app, w, sheet_path) -> None:
    """Sheet source with Unpack's slicing options, playback controls, filmstrip and sprite source."""
    from sprite_tool.core import ONCE, PING_PONG
    from sprite_tool.ui.tabs.animate_tab import SOURCE_SHEET, SOURCE_SPRITES

    a = w.animate
    w.tabs.setCurrentWidget(a)
    pump(app)
    assert a.source == SOURCE_SHEET
    assert type(a.slicer.form) is type(w.unpack.slicer.form), "sheet mode must use the same slicing form"

    f = a.slicer.form
    for box, value in ((f.offset_x, 4), (f.offset_y, 4), (f.gap_x, 2), (f.gap_y, 2)):
        box.setValue(value)
    a.slicer.load_sheet(sheet_path)
    a.rebuild_frames()
    pump(app)
    assert len(a._frames) == 21 and a.strip.count() == 21

    # Showing a frame updates the view, filmstrip highlight, counter and the cell on the sheet.
    a.show_frame(5)
    assert a.strip.currentRow() == 5 and a.controls.frame_label.text() == "Frame 6 / 21"
    assert a.slicer.view._highlight_item is not None

    # Play / tick / pause.
    a.play()
    assert a.playing and a.controls.play_btn.isChecked()
    a._tick()
    assert a.current_index == 6

    # Clicking a filmstrip frame pauses on it; double-clicking plays from it.
    strip_point = a.strip.visualItemRect(a.strip.item(10)).center()
    QTest.mouseClick(a.strip.viewport(), Qt.LeftButton, Qt.NoModifier, strip_point)
    pump(app)
    assert not a.playing and a.current_index == 10, (a.playing, a.current_index)
    # A real double-click is press/release then double-click; Qt 6's mouseDClick alone skips the press.
    frame3 = a.strip.visualItemRect(a.strip.item(3)).center()
    QTest.mouseClick(a.strip.viewport(), Qt.LeftButton, Qt.NoModifier, frame3)
    QTest.mouseDClick(a.strip.viewport(), Qt.LeftButton, Qt.NoModifier, frame3)
    pump(app)
    assert a.playing and a.current_index == 3, (a.playing, a.current_index)

    # Speed control changes the live timer; real time actually advances frames.
    a.controls.fps.setValue(50)
    assert a._play_timer.interval() == 20
    start = a.current_index
    QTest.qWait(250)
    assert a.current_index != start, "playback did not advance in real time"

    # Play-once stops at the last frame; ping-pong bounces.
    a.controls.mode.setCurrentIndex(a.controls.mode.findData(ONCE))
    a.show_frame(20)
    a._tick()
    assert not a.playing and a.current_index == 20
    a.controls.mode.setCurrentIndex(a.controls.mode.findData(PING_PONG))
    a.play()
    a._tick()
    assert a.current_index == 19, a.current_index   # bounced back off the last frame
    a.pause()

    # Leaving the tab pauses playback.
    a.play()
    w.tabs.setCurrentWidget(w.pack)
    pump(app)
    assert not a.playing, "playback should pause when the tab is hidden"
    w.tabs.setCurrentWidget(a)

    # Sprites source: frames of different sizes share one canvas.
    a.source_switch.set_current(SOURCE_SPRITES)
    small = w.unpack.sprites[0].image.crop((0, 0, 16, 24))
    a.sprite_list.add_images([("big", w.unpack.sprites[1].image), ("small", small)])
    a.rebuild_frames()
    assert len(a._frames) == 2 and a._frames[0].size() == a._frames[1].size()

    a.source_switch.set_current(SOURCE_SHEET)
    a.rebuild_frames()
    a.show_frame(7)
    pump(app, 20)
    w.grab().save(os.path.join(OUT, "shot_animate.png"))


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
    check_sprite_editor(app, w)
    check_animate(app, w, sheet_path)
    check_preview(app, w)
    w.close()
    print("ui OK")


if __name__ == "__main__":
    main()
