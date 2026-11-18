"""A sprite sheet viewer with the 'How to slice' settings.

Used by the Unpack tab and the Animate tab's "Sprite sheet" mode, so both slice
sheets in exactly the same way.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QVBoxLayout, QWidget

from ... import APP_NAME
from ...core import Rect, Sprite, load_rgba, slice_sheet
from .. import file_dialogs, prefs
from ..forms import SliceSettingsForm
from ..qt_image import pil_to_pixmap
from ..theme import error_html
from ..widgets import ImageView, ZoomBar, hint_label, pane_title, primary_button

RESLICE_DELAY_MS = 120
PLACEHOLDER = "Drop a sprite sheet here\nor click to choose a file"


class SheetSlicerPanel(QWidget):
    sliced = Signal()                    # .cells / .sprites were updated
    sheetLoaded = Signal(str)            # path of the new sheet
    spriteClicked = Signal(int, object)  # index into .sprites (-1 = no sprite there), keyboard modifiers
    status = Signal(str)

    def __init__(self, title: str = "Sprite sheet"):
        super().__init__()
        self.sheet: Image.Image | None = None
        self.cells: list[Rect] = []
        self.sprites: list[Sprite] = []

        self._reslice_timer = QTimer(self, singleShot=True, interval=RESLICE_DELAY_MS)
        self._reslice_timer.timeout.connect(self.reslice)
        self._build(title)

    def _build(self, title: str) -> None:
        self.view = ImageView(PLACEHOLDER)
        self.view.filesDropped.connect(lambda paths: self.load_sheet(paths[0]))
        self.view.emptyClicked.connect(self.open_dialog)
        self.view.sceneClicked.connect(self._on_view_clicked)

        open_btn = primary_button("Open sheet…")
        open_btn.clicked.connect(self.open_dialog)
        header = QHBoxLayout()
        header.addWidget(pane_title(title))
        header.addStretch()
        header.addWidget(ZoomBar(self.view))
        header.addWidget(open_btn)

        self.file_label = hint_label("No sheet loaded", wrap=False)
        self.form = SliceSettingsForm()
        self.form.changed.connect(self._schedule_reslice)
        self.slice_info = hint_label(wrap=False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(header)
        lay.addWidget(self.file_label)
        lay.addWidget(self.view, 1)
        lay.addWidget(self.form)
        lay.addWidget(self.slice_info)

    # ================================================================ loading
    def open_dialog(self) -> None:
        path = file_dialogs.ask_open_image(self, "Open sprite sheet")
        if path:
            self.load_sheet(path)

    def load_sheet(self, path: str) -> None:
        try:
            img = load_rgba(path)
        except Exception as exc:  # noqa: BLE001 - any decoder error should reach the user
            QMessageBox.warning(self, APP_NAME, f"Could not open the image:\n{path}\n\n{exc}")
            return
        prefs.remember_dir(path)
        self.sheet = img
        self.view.set_pixmap(pil_to_pixmap(img))
        self.file_label.setText(f"{Path(path).name}  ·  {img.width} × {img.height} px")
        self.sheetLoaded.emit(path)
        self.reslice()
        self.status.emit(f"Opened {path}")

    # ================================================================ slicing
    def _schedule_reslice(self) -> None:
        if self.sheet is not None:
            self._reslice_timer.start()   # debounce rapid spin-box changes

    def reslice(self) -> None:
        if self.sheet is None:
            return
        try:
            cells, sprites = slice_sheet(self.sheet, self.form.settings())
        except ValueError as exc:
            self.slice_info.setText(error_html(str(exc)))
            return
        self.cells, self.sprites = cells, sprites
        self.view.set_grid(cells)
        self.view.set_highlight([])
        if cells:
            skipped = len(cells) - len(sprites)
            extra = f" · {skipped} empty skipped" if skipped else ""
            self.slice_info.setText(f"{len(cells)} cells of {cells[0].w} × {cells[0].h} px{extra}")
        else:
            self.slice_info.setText(error_html("No cells fit. Check the size, offset and gap."))
        self.sliced.emit()

    # ================================================================ selection display
    def sprite_index_at(self, x: float, y: float) -> int:
        return next((i for i, s in enumerate(self.sprites) if s.cell.contains(x, y)), -1)

    def highlight(self, indices) -> None:
        """Mark these sprites' cells on the sheet."""
        self.view.set_highlight(self.sprites[i].cell for i in indices if 0 <= i < len(self.sprites))

    def _on_view_clicked(self, x: float, y: float, modifiers) -> None:
        self.spriteClicked.emit(self.sprite_index_at(x, y), modifiers)
