"""'Layout' panel for the Pack tab."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
)

from ...core import ALIGN_BOTTOM, ALIGN_CENTER, ALIGN_TOP_LEFT, ORDER_COLS, ORDER_ROWS, PackSettings
from .. import theme
from ..widgets import spin_box

MAX_PX = 16384
MAX_SPACING = 4096
MAX_CELLS_PER_AXIS = 1000
DEFAULT_SOLID = QColor(255, 0, 255)   # magenta: the classic "key" background

ALIGN_CHOICES = (("Center", ALIGN_CENTER), ("Bottom center", ALIGN_BOTTOM), ("Top-left", ALIGN_TOP_LEFT))
ORDER_CHOICES = (("Row by row (→ then ↓)", ORDER_ROWS), ("Column by column (↓ then →)", ORDER_COLS))
BG_TRANSPARENT, BG_SOLID = 0, 1


class PackLayoutForm(QGroupBox):
    changed = Signal()             # anything affecting the packed image
    gridToggled = Signal(bool)     # only the overlay changed

    def __init__(self):
        super().__init__("Layout")
        self.bg_color = QColor(DEFAULT_SOLID)
        self._create_widgets()
        self._lay_out()
        self._connect()
        self._refresh_swatch()

    # ------------------------------------------------------------ build
    def _create_widgets(self) -> None:
        self.cols = spin_box(0, MAX_CELLS_PER_AXIS, 0, suffix="", special="Auto")
        self.rows = spin_box(0, MAX_CELLS_PER_AXIS, 0, suffix="", special="Auto")
        self.cell_w = spin_box(0, MAX_PX, 0, special="Auto (largest)")
        self.cell_h = spin_box(0, MAX_PX, 0, special="Auto (largest)")
        self.gap = spin_box(0, MAX_SPACING, 0)
        self.margin = spin_box(0, MAX_SPACING, 0)

        self.align = QComboBox()
        for label, key in ALIGN_CHOICES:
            self.align.addItem(label, key)
        self.order = QComboBox()
        for label, key in ORDER_CHOICES:
            self.order.addItem(label, key)

        self.background = QComboBox()
        self.background.addItems(["Transparent", "Solid color"])
        self.swatch = QPushButton()
        self.swatch.setFixedWidth(44)
        self.swatch.setToolTip("Pick the background color")

        self.show_grid = QCheckBox("Show cell grid")
        self.show_grid.setChecked(True)

    def _lay_out(self) -> None:
        g = QGridLayout(self)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(6)
        rows = (
            ("Columns", self.cols, "Rows", self.rows),
            ("Cell width", self.cell_w, "Cell height", self.cell_h),
            ("Gap", self.gap, "Margin", self.margin),
            ("Align in cell", self.align, "Fill order", self.order),
        )
        for r, (l1, w1, l2, w2) in enumerate(rows):
            g.addWidget(QLabel(l1), r, 0)
            g.addWidget(w1, r, 1)
            g.addWidget(QLabel(l2), r, 2)
            g.addWidget(w2, r, 3)
        bg_row = QHBoxLayout()
        bg_row.addWidget(self.background, 1)
        bg_row.addWidget(self.swatch)
        g.addWidget(QLabel("Background"), 4, 0)
        g.addLayout(bg_row, 4, 1)
        g.addWidget(self.show_grid, 4, 2, 1, 2)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)

    def _connect(self) -> None:
        for sb in (self.cols, self.rows, self.cell_w, self.cell_h, self.gap, self.margin):
            sb.valueChanged.connect(self.changed)
        for cb in (self.align, self.order, self.background):
            cb.currentIndexChanged.connect(self.changed)
        self.background.currentIndexChanged.connect(self._refresh_swatch)
        self.swatch.clicked.connect(self._pick_color)
        self.show_grid.toggled.connect(self.gridToggled)

    # ------------------------------------------------------------ background color
    def _pick_color(self) -> None:
        c = QColorDialog.getColor(self.bg_color, self, "Background color", QColorDialog.ShowAlphaChannel)
        if not c.isValid():
            return
        self.bg_color = c
        if self.background.currentIndex() == BG_SOLID:
            self._refresh_swatch()
            self.changed.emit()
        else:
            self.background.setCurrentIndex(BG_SOLID)   # emits changed and refreshes the swatch

    def _refresh_swatch(self) -> None:
        solid = self.background.currentIndex() == BG_SOLID
        c = self.bg_color if solid else theme.SWATCH_NONE
        self.swatch.setStyleSheet(f"background:{c.name()}; border:1px solid #666; border-radius:4px;")

    # ------------------------------------------------------------ value
    def settings(self) -> PackSettings:
        bg = (0, 0, 0, 0)
        if self.background.currentIndex() == BG_SOLID:
            c = self.bg_color
            bg = (c.red(), c.green(), c.blue(), c.alpha())
        return PackSettings(
            cols=self.cols.value(), rows=self.rows.value(),
            cell_w=self.cell_w.value(), cell_h=self.cell_h.value(),
            padding=self.gap.value(), margin=self.margin.value(),
            align=self.align.currentData(), order=self.order.currentData(),
            background=bg,
        )
