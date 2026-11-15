"""Smoke test: checks slicing/packing math, then drives the UI offscreen and saves screenshots.

Run from the project folder:  .venv\\Scripts\\python.exe tests\\smoke_test.py
Screenshots land in tests/out/.
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "tests", "out")
os.makedirs(SP, exist_ok=True)
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
from PIL import Image, ImageDraw
import sprite_core as core

# sample sheet: 6x4 cells of 32x32, gap 2, offset 4, last 3 cells empty
sheet = Image.new("RGBA", (4 + 6*32 + 5*2, 4 + 4*32 + 3*2), (0,0,0,0))
d = ImageDraw.Draw(sheet)
cols = [(255,90,90),(90,200,120),(90,140,255),(255,200,60),(200,100,255),(60,220,220)]
for i in range(21):
    r, c = divmod(i, 6)
    x, y = 4 + c*34, 4 + r*34
    d.ellipse((x+4, y+4+(i%3), x+27, y+27), fill=cols[i%6]+(255,), outline=(20,20,20,255))
    d.text((x+11, y+10), str(i), fill=(0,0,0,255))
sheet.save(f"{SP}/sample_sheet.png")

s = core.SliceSettings(mode="size", cell_w=32, cell_h=32, offset_x=4, offset_y=4, spacing_x=2, spacing_y=2)
cells, sprites = core.slice_sheet(sheet, s)
assert len(cells) == 24 and len(sprites) == 21, (len(cells), len(sprites))
assert (cells[7].x, cells[7].y) == (4+34, 4+34)
s.mode="grid"; s.cols=6; s.rows=4
cells, sprites = core.slice_sheet(sheet, s)
assert len(cells) == 24 and cells[0].w == 32 and len(sprites) == 21, (cells[0], len(sprites))
s.corner = "br"; s.mode="size"; s.offset_x=s.offset_y=0
cells,_ = core.slice_sheet(sheet, s)
assert cells[0].x + cells[0].w == sheet.width and cells[0].y + cells[0].h == sheet.height
s.trim=True; s.corner="tl"; s.offset_x=s.offset_y=4
_, sp = core.slice_sheet(sheet, s)
assert sp[0].image.width < 32
r = core.pack_sprites([x.image for x in sprites], [f"s{i}" for i in range(21)], core.PackSettings(cols=7, padding=1, margin=2))
assert (r.cols, r.rows) == (7, 3) and r.image.width == 2*2 + 7*32 + 6
try: core.pack_sprites([x.image for x in sprites], [], core.PackSettings(cols=2, rows=2)); raise SystemExit("expected error")
except ValueError: pass
print("core OK")

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
import main as m
app = QApplication([]); app.setStyle("Fusion"); app.setPalette(m.dark_palette()); app.setStyleSheet(m.STYLE)
w = m.MainWindow(); w.resize(1360, 860); w.show(); w.tabs.setCurrentIndex(0)
u = w.unpack
u.sp_ox.setValue(4); u.sp_oy.setValue(4); u.sp_sx.setValue(2); u.sp_sy.setValue(2)
u.load_sheet(f"{SP}/sample_sheet.png")
for _ in range(20): app.processEvents()
assert u.list.count() == 21, u.list.count()
u.list.item(2).setSelected(True); u.list.item(8).setSelected(True)
u._on_sheet_clicked(4+34*3+5, 4+5, Qt.ControlModifier)  # ctrl-click cell 3 on the sheet
assert sorted(u.selected_rows()) == [2,3,8], u.selected_rows()
for _ in range(20): app.processEvents()
w.grab().save(f"{SP}/shot_unpack.png")
u._send_to_pack()
p = w.pack
p.move_selected  # exists
p.list.item(0).setSelected(True); p.move_selected(1)
assert p._entry(1)["name"].endswith("_02"), p._entry(1)["name"]
p.repack()
assert p.result is not None and len(p.result.frames) == 3
p.list.clearSelection(); p.list.item(0).setSelected(True); p.move_selected(10**9)
p.sp_cols.setValue(3); p.repack()
for _ in range(20): app.processEvents()
w.grab().save(f"{SP}/shot_pack.png")
# full sheet into pack for a nicer screenshot
p.list.clear(); p.entries.clear()
u.list.clearSelection(); u._send_to_pack(); p.sp_cols.setValue(7); p.sp_pad.setValue(2); p.repack()
for _ in range(30): app.processEvents()
w.grab().save(f"{SP}/shot_pack2.png")
dlg = m.PreviewDialog(w, u.sprites[0].image, u.name_for(0), lambda: None); dlg.show()
for _ in range(10): app.processEvents()
dlg.grab().save(f"{SP}/shot_preview.png")
print("ui OK", p.result.image.size)
