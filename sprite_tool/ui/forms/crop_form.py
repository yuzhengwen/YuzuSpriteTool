"""'Crop' panel for the sprite editor."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton

from ...core import Rect, clamp_rect
from ..widgets import hint_label, spin_box


class CropForm(QGroupBox):
    """Checkable group: unchecked means 'no crop'. Values are kept inside the image."""

    changed = Signal()
    trimRequested = Signal()

    def __init__(self):
        super().__init__("Crop")
        self.setCheckable(True)
        self.setChecked(False)
        self._img_w = self._img_h = 1

        self.x_box = spin_box(0, 0, 0)
        self.y_box = spin_box(0, 0, 0)
        self.w_box = spin_box(1, 1, 1)
        self.h_box = spin_box(1, 1, 1)
        trim_btn = QPushButton("Trim transparent")
        trim_btn.setToolTip("Crop to the visible pixels.")
        trim_btn.clicked.connect(self.trimRequested)
        full_btn = QPushButton("Full image")
        full_btn.clicked.connect(lambda: self.set_rect(Rect(0, 0, self._img_w, self._img_h)))

        g = QGridLayout(self)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(6)
        for row, (l1, w1, l2, w2) in enumerate((("X", self.x_box, "Y", self.y_box), ("Width", self.w_box, "Height", self.h_box))):
            g.addWidget(QLabel(l1), row, 0)
            g.addWidget(w1, row, 1)
            g.addWidget(QLabel(l2), row, 2)
            g.addWidget(w2, row, 3)
        buttons = QHBoxLayout()
        buttons.addWidget(trim_btn)
        buttons.addWidget(full_btn)
        g.addLayout(buttons, 2, 0, 1, 4)
        g.addWidget(hint_label("Or drag on the image to draw the area."), 3, 0, 1, 4)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)

        # Width/height can never reach past the image edge from the current X/Y.
        self.x_box.valueChanged.connect(lambda v: self.w_box.setMaximum(self._img_w - v))
        self.y_box.valueChanged.connect(lambda v: self.h_box.setMaximum(self._img_h - v))
        for sb in (self.x_box, self.y_box, self.w_box, self.h_box):
            sb.valueChanged.connect(self._emit_changed)
        self.toggled.connect(self._emit_changed)

    def _emit_changed(self, *_):
        self.changed.emit()

    def set_image_size(self, w: int, h: int) -> None:
        self._img_w, self._img_h = w, h
        self._apply(Rect(0, 0, w, h))

    def _apply(self, rect: Rect) -> None:
        rect = clamp_rect(rect, self._img_w, self._img_h)
        for sb in (self.x_box, self.y_box, self.w_box, self.h_box):
            sb.blockSignals(True)
        self.x_box.setRange(0, self._img_w - 1)
        self.y_box.setRange(0, self._img_h - 1)
        self.x_box.setValue(rect.x)
        self.y_box.setValue(rect.y)
        self.w_box.setRange(1, self._img_w - rect.x)
        self.h_box.setRange(1, self._img_h - rect.y)
        self.w_box.setValue(rect.w)
        self.h_box.setValue(rect.h)
        for sb in (self.x_box, self.y_box, self.w_box, self.h_box):
            sb.blockSignals(False)

    def set_rect(self, rect: Rect, activate: bool = True) -> None:
        """Set the area (emits `changed` once). Turns cropping on unless activate=False."""
        self._apply(rect)
        if activate and not self.isChecked():
            self.setChecked(True)   # emits changed via toggled
        else:
            self.changed.emit()

    def crop_rect(self) -> Rect:
        return clamp_rect(Rect(self.x_box.value(), self.y_box.value(), self.w_box.value(), self.h_box.value()),
                          self._img_w, self._img_h)

    def active_rect(self) -> Rect | None:
        return self.crop_rect() if self.isChecked() else None
