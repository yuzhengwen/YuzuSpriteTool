"""Fit / 1:1 / zoom out / zoom in buttons for an ImageView."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from .image_view import ImageView

BUTTON_STEP = 1.5


class ZoomBar(QWidget):
    def __init__(self, view: ImageView):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        buttons = (
            ("Fit", "Fit to view", view.fit),
            ("1:1", "Actual pixels", lambda: view.set_zoom(1)),
            ("−", "Zoom out", lambda: view.zoom_by(1 / BUTTON_STEP)),
            ("+", "Zoom in", lambda: view.zoom_by(BUTTON_STEP)),
        )
        for text, tip, action in buttons:
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFixedWidth(40 if len(text) > 1 else 30)
            b.clicked.connect(action)
            lay.addWidget(b)
