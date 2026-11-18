"""'Resize' panel for the sprite editor."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton

from ...core import (
    RESAMPLE_BICUBIC, RESAMPLE_BILINEAR, RESAMPLE_LANCZOS, RESAMPLE_NEAREST,
)
from ...core.editing import MAX_EDIT_SIZE
from ..widgets import spin_box

MAX_SCALE_PERCENT = 10_000
SCALE_PRESETS = ((50, "½×"), (200, "2×"), (300, "3×"), (400, "4×"))
RESAMPLE_CHOICES = (
    ("Nearest (crisp pixel art)", RESAMPLE_NEAREST),
    ("Bilinear", RESAMPLE_BILINEAR),
    ("Bicubic", RESAMPLE_BICUBIC),
    ("Lanczos (smoothest)", RESAMPLE_LANCZOS),
)


class ResizeForm(QGroupBox):
    """Checkable group: unchecked means 'keep the cropped size'.

    Width, height and scale % stay in sync. The base size (100 %) is the cropped size,
    which the editor updates whenever the crop changes.
    """

    changed = Signal()

    def __init__(self):
        super().__init__("Resize")
        self.setCheckable(True)
        self.setChecked(False)
        self._base = (1, 1)
        self._syncing = False

        self.width_box = spin_box(1, MAX_EDIT_SIZE, 1)
        self.height_box = spin_box(1, MAX_EDIT_SIZE, 1)
        self.scale_box = spin_box(1, MAX_SCALE_PERCENT, 100, suffix=" %")
        self.keep_aspect = QCheckBox("Keep aspect ratio")
        self.keep_aspect.setChecked(True)
        self.resample_box = QComboBox()
        for label, key in RESAMPLE_CHOICES:
            self.resample_box.addItem(label, key)

        presets = QHBoxLayout()
        for percent, label in SCALE_PRESETS:
            b = QPushButton(label)
            b.setToolTip(f"Scale to {percent} %")
            b.clicked.connect(lambda _=False, p=percent: self._apply_scale(p))
            presets.addWidget(b)

        g = QGridLayout(self)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(6)
        g.addWidget(QLabel("Width"), 0, 0)
        g.addWidget(self.width_box, 0, 1)
        g.addWidget(QLabel("Height"), 0, 2)
        g.addWidget(self.height_box, 0, 3)
        g.addWidget(QLabel("Scale"), 1, 0)
        g.addWidget(self.scale_box, 1, 1)
        g.addWidget(self.keep_aspect, 1, 2, 1, 2)
        g.addLayout(presets, 2, 0, 1, 4)
        g.addWidget(QLabel("Smoothing"), 3, 0)
        g.addWidget(self.resample_box, 3, 1, 1, 3)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)

        self.width_box.valueChanged.connect(self._on_width)
        self.height_box.valueChanged.connect(self._on_height)
        self.scale_box.valueChanged.connect(self._on_scale)
        self.keep_aspect.toggled.connect(self._on_keep_aspect)
        self.resample_box.currentIndexChanged.connect(self._emit_changed)
        self.toggled.connect(self._on_toggled)

    # ------------------------------------------------------------ syncing
    def _emit_changed(self, *_):
        self.changed.emit()

    def _set_values(self, w: int, h: int, scale: int | None = None) -> None:
        self._syncing = True
        self.width_box.setValue(max(1, w))
        self.height_box.setValue(max(1, h))
        bw = self._base[0]
        self.scale_box.setValue(scale if scale is not None else max(1, round(self.width_box.value() * 100 / bw)))
        self._syncing = False

    def _on_width(self, w: int) -> None:
        if self._syncing:
            return
        bw, bh = self._base
        h = round(w * bh / bw) if self.keep_aspect.isChecked() else self.height_box.value()
        self._set_values(w, h)
        self.changed.emit()

    def _on_height(self, h: int) -> None:
        if self._syncing:
            return
        bw, bh = self._base
        w = round(h * bw / bh) if self.keep_aspect.isChecked() else self.width_box.value()
        self._set_values(w, h)
        self.changed.emit()

    def _on_scale(self, percent: int) -> None:
        if not self._syncing:
            self._apply_scale(percent)

    def _apply_scale(self, percent: int) -> None:
        bw, bh = self._base
        self._set_values(round(bw * percent / 100), round(bh * percent / 100), percent)
        if not self.isChecked():
            self.setChecked(True)   # a preset implies resizing; emits changed
        else:
            self.changed.emit()

    def _on_keep_aspect(self, keep: bool) -> None:
        if keep:
            self._on_width(self.width_box.value())   # snap height back to the ratio

    def _on_toggled(self, on: bool) -> None:
        if not on:
            self._set_values(*self._base, 100)
        self.changed.emit()

    # ------------------------------------------------------------ public
    def set_base_size(self, w: int, h: int) -> None:
        """The cropped size changed. While inactive, the fields simply mirror it."""
        old_base = self._base
        self._base = (max(1, w), max(1, h))
        if not self.isChecked():
            self._set_values(*self._base, 100)
        elif self._base != old_base and self.keep_aspect.isChecked():
            # Keep the current scale so the result follows the new crop proportionally.
            self._set_values(round(self._base[0] * self.scale_box.value() / 100),
                             round(self._base[1] * self.scale_box.value() / 100), self.scale_box.value())
        else:
            self._set_values(self.width_box.value(), self.height_box.value())

    def set_state(self, size: tuple[int, int] | None, resample: str) -> None:
        index = self.resample_box.findData(resample)
        self.resample_box.setCurrentIndex(max(0, index))
        if size is None:
            self.setChecked(False)
            return
        bw, bh = self._base
        keep = abs(size[0] * bh - size[1] * bw) <= max(bw, bh)   # ratio preserved within rounding
        self.keep_aspect.blockSignals(True)
        self.keep_aspect.setChecked(keep)
        self.keep_aspect.blockSignals(False)
        self.blockSignals(True)
        self.setChecked(True)
        self.blockSignals(False)
        self._set_values(*size)
        self.changed.emit()

    def target_size(self) -> tuple[int, int] | None:
        return (self.width_box.value(), self.height_box.value()) if self.isChecked() else None

    def resample(self) -> str:
        return self.resample_box.currentData()
