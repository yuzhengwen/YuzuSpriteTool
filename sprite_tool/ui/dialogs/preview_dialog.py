"""Popup that shows one sprite at full size."""
from __future__ import annotations

import math
from typing import Callable

from PIL import Image
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..qt_image import copy_to_clipboard, pil_to_pixmap
from ..widgets import ImageView, ZoomBar, primary_button

SCREEN_FRACTION = 0.7   # how much of the screen the image may take when opened


class PreviewDialog(QDialog):
    def __init__(self, parent: QWidget, img: Image.Image, name: str, on_save: Callable[[], None]):
        super().__init__(parent)
        self.setWindowTitle(f"{name}  ({img.width} × {img.height} px)")

        self.view = ImageView(accept_drops=False)
        self.view.set_pixmap(pil_to_pixmap(img), fit=True)   # refits whenever the dialog resizes

        info = QLabel(f"<b>{name}</b> &nbsp; {img.width} × {img.height} px &nbsp;·&nbsp; scroll to zoom, drag to pan")
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(lambda: copy_to_clipboard(img))
        save_btn = primary_button("Save PNG…")
        save_btn.clicked.connect(on_save)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)

        bottom = QHBoxLayout()
        bottom.addWidget(ZoomBar(self.view))
        bottom.addStretch()
        for b in (copy_btn, save_btn, close_btn):
            bottom.addWidget(b)

        lay = QVBoxLayout(self)
        lay.addWidget(info)
        lay.addWidget(self.view, 1)
        lay.addLayout(bottom)
        self._size_to(img)

    def _size_to(self, img: Image.Image) -> None:
        """Open big enough to show the sprite at a crisp whole-number zoom."""
        screen = self.screen().availableGeometry()
        target = min(screen.width(), screen.height()) * SCREEN_FRACTION
        z = target / max(img.width, img.height)
        if z >= 1:
            z = math.floor(z)
        w = int(min(max(img.width * z + 60, 460), screen.width() * 0.9))
        h = int(min(max(img.height * z + 130, 340), screen.height() * 0.9))
        self.resize(w, h)
