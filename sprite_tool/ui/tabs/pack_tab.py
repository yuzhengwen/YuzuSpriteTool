"""Pack tab: collect and order sprites (left) and build the combined sheet (right)."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSplitter, QVBoxLayout, QWidget

from ...core import PackResult, pack_metadata, pack_sprites
from .. import file_dialogs
from ..forms import PackLayoutForm
from ..panels import SpriteListPanel
from ..qt_image import pil_to_pixmap
from ..theme import error_html
from ..widgets import ImageView, ZoomBar, hint_label, pane_title, primary_button

REPACK_DELAY_MS = 120


class PackTab(QWidget):
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self.result: PackResult | None = None
        self._repack_timer = QTimer(self, singleShot=True, interval=REPACK_DELAY_MS)
        self._repack_timer.timeout.connect(self.repack)

        self.sprites = SpriteListPanel()
        self.sprites.layout().setContentsMargins(0, 0, 6, 0)
        self.sprites.changed.connect(self._schedule_repack)
        self.sprites.status.connect(self.status)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.sprites)
        splitter.addWidget(self._build_sheet_pane())
        splitter.setSizes([480, 820])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(splitter)
        self._update_export_buttons()

    # Entry points used by the main window (Ctrl+O, "Send to Pack tab").
    def open_dialog(self) -> None:
        self.sprites.add_dialog()

    def add_images(self, items) -> None:
        self.sprites.add_images(items)

    # ================================================================ layout
    def _build_sheet_pane(self) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(6, 0, 0, 0)

        self.view = ImageView("The packed sprite sheet shows up here")
        self.view.filesDropped.connect(self.sprites.add_files)
        self.view.emptyClicked.connect(self.sprites.add_dialog)
        header = QHBoxLayout()
        header.addWidget(pane_title("Packed sheet"))
        header.addStretch()
        header.addWidget(ZoomBar(self.view))

        self.info = hint_label(wrap=False)
        self.form = PackLayoutForm()
        self.form.changed.connect(self._schedule_repack)
        self.form.gridToggled.connect(self._update_grid_overlay)

        self.export_btn = QPushButton("Export PNG…")
        self.export_btn.clicked.connect(lambda: self.export(with_json=False))
        self.export_json_btn = primary_button("Export PNG + JSON…")
        self.export_json_btn.setToolTip("Also writes a .json file with each frame's name and position.")
        self.export_json_btn.clicked.connect(lambda: self.export(with_json=True))
        export_row = QHBoxLayout()
        export_row.addStretch()
        export_row.addWidget(self.export_btn)
        export_row.addWidget(self.export_json_btn)

        lay.addLayout(header)
        lay.addWidget(self.info)
        lay.addWidget(self.view, 1)
        lay.addWidget(self.form)
        lay.addLayout(export_row)
        return pane

    # ================================================================ packing
    def _schedule_repack(self) -> None:
        self._repack_timer.start()

    def repack(self) -> None:
        entries = self.sprites.entries()
        if not entries:
            self._show_result(None, "")
            self.view.clear_image()
            return
        try:
            result = pack_sprites([e.image for e in entries], [e.name for e in entries], self.form.settings())
        except ValueError as exc:
            self._show_result(None, error_html(str(exc)))
            return
        keep_view = self.result is not None and not self.view.auto_fit
        self.view.set_pixmap(pil_to_pixmap(result.image), fit=not keep_view)
        self._show_result(result, self._describe(result))
        self._update_grid_overlay()

    @staticmethod
    def _describe(r: PackResult) -> str:
        text = (f"{r.image.width} × {r.image.height} px  ·  {r.cols} columns × {r.rows} rows"
                f"  ·  cell {r.cell_w} × {r.cell_h} px")
        if r.empty_cells:
            text += f" · {r.empty_cells} empty cell{'s' if r.empty_cells != 1 else ''}"
        return text

    def _show_result(self, result: PackResult | None, info: str) -> None:
        self.result = result
        self.info.setText(info)
        self._update_export_buttons()

    def _update_export_buttons(self) -> None:
        can_export = self.result is not None
        self.export_btn.setEnabled(can_export)
        self.export_json_btn.setEnabled(can_export)

    def _update_grid_overlay(self) -> None:
        if self.result is not None:
            self.view.set_grid(self.result.cells if self.form.show_grid.isChecked() else [])

    def export(self, with_json: bool) -> None:
        if self.result is None:
            return
        path = file_dialogs.ask_save_png(self, "Export sprite sheet", "spritesheet")
        if not path:
            return
        self.result.image.save(path)
        message = f"Saved {path}"
        if with_json:
            json_path = Path(path).with_suffix(".json")
            meta = pack_metadata(self.result, Path(path).name, self.form.settings())
            json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            message += f" and {json_path.name}"
        self.status.emit(message)
