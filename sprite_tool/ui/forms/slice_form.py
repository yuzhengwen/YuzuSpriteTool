"""'How to slice' panel for the Unpack tab."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QComboBox, QGridLayout, QGroupBox, QLabel, QRadioButton

from ...core import MODE_GRID, MODE_SIZE, SliceSettings
from ..widgets import separator, spin_box

MAX_PX = 16384
MAX_CELLS_PER_AXIS = 1000

CORNER_CHOICES = (("Top-left", "tl"), ("Top-right", "tr"), ("Bottom-left", "bl"), ("Bottom-right", "br"))
OFFSET_GAP_TIP = "Offset: where cutting starts, measured from the start corner.\nGap: empty space between cells."


class SliceSettingsForm(QGroupBox):
    changed = Signal()

    def __init__(self):
        super().__init__("How to slice")
        self._create_widgets()
        self._lay_out()
        self._connect()
        self._update_mode()

    # ------------------------------------------------------------ build
    def _create_widgets(self) -> None:
        self.by_size = QRadioButton("Fixed cell size")
        self.by_grid = QRadioButton("Columns × rows")
        self.by_size.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.by_size)
        group.addButton(self.by_grid)

        self.cell_w = spin_box(1, MAX_PX, 32)
        self.cell_h = spin_box(1, MAX_PX, 32)
        self.cols = spin_box(1, MAX_CELLS_PER_AXIS, 4, suffix="")
        self.rows = spin_box(1, MAX_CELLS_PER_AXIS, 4, suffix="")
        self.offset_x = spin_box(0, MAX_PX, 0)
        self.offset_y = spin_box(0, MAX_PX, 0)
        self.gap_x = spin_box(0, MAX_PX, 0)
        self.gap_y = spin_box(0, MAX_PX, 0)
        for sb in (self.offset_x, self.offset_y, self.gap_x, self.gap_y):
            sb.setToolTip(OFFSET_GAP_TIP)

        self.corner = QComboBox()
        for label, key in CORNER_CHOICES:
            self.corner.addItem(label, key)

        self.keep_partial = QCheckBox("Keep cut-off edge cells")
        self.keep_partial.setToolTip("Fixed cell size only: keep cells at the far edges that are smaller than a full cell.")
        self.skip_empty = QCheckBox("Skip empty cells")
        self.skip_empty.setChecked(True)
        self.skip_empty.setToolTip("Drop cells that are fully transparent.")
        self.trim = QCheckBox("Trim transparent edges")
        self.trim.setToolTip("Crop each sprite to its visible pixels.")

    def _lay_out(self) -> None:
        g = QGridLayout(self)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(6)
        g.addWidget(self.by_size, 0, 0, 1, 2)
        g.addWidget(self.by_grid, 0, 2, 1, 2)
        self._pair(g, 1, "Width", self.cell_w, "Columns", self.cols)
        self._pair(g, 2, "Height", self.cell_h, "Rows", self.rows)
        g.addWidget(separator(), 3, 0, 1, 4)
        g.addWidget(QLabel("Start from"), 4, 0)
        g.addWidget(self.corner, 4, 1)
        self._pair(g, 5, "Offset X", self.offset_x, "Offset Y", self.offset_y)
        self._pair(g, 6, "Gap X", self.gap_x, "Gap Y", self.gap_y)
        g.addWidget(self.skip_empty, 7, 0, 1, 2)
        g.addWidget(self.trim, 7, 2, 1, 2)
        g.addWidget(self.keep_partial, 8, 0, 1, 4)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)

    @staticmethod
    def _pair(g: QGridLayout, row: int, left_label: str, left, right_label: str, right) -> None:
        g.addWidget(QLabel(left_label), row, 0)
        g.addWidget(left, row, 1)
        g.addWidget(QLabel(right_label), row, 2)
        g.addWidget(right, row, 3)

    def _connect(self) -> None:
        self.by_size.toggled.connect(self._update_mode)
        for sb in (self.cell_w, self.cell_h, self.cols, self.rows,
                   self.offset_x, self.offset_y, self.gap_x, self.gap_y):
            sb.valueChanged.connect(self.changed)
        for ck in (self.keep_partial, self.skip_empty, self.trim, self.by_size):
            ck.toggled.connect(self.changed)
        self.corner.currentIndexChanged.connect(self.changed)

    def _update_mode(self) -> None:
        """Enable only the inputs that apply to the chosen slicing mode."""
        size_mode = self.by_size.isChecked()
        for w in (self.cell_w, self.cell_h, self.keep_partial):
            w.setEnabled(size_mode)
        for w in (self.cols, self.rows):
            w.setEnabled(not size_mode)

    # ------------------------------------------------------------ value
    def settings(self) -> SliceSettings:
        return SliceSettings(
            mode=MODE_SIZE if self.by_size.isChecked() else MODE_GRID,
            cell_w=self.cell_w.value(), cell_h=self.cell_h.value(),
            cols=self.cols.value(), rows=self.rows.value(),
            offset_x=self.offset_x.value(), offset_y=self.offset_y.value(),
            spacing_x=self.gap_x.value(), spacing_y=self.gap_y.value(),
            corner=self.corner.currentData(),
            include_partial=self.keep_partial.isChecked(),
            skip_empty=self.skip_empty.isChecked(),
            trim=self.trim.isChecked(),
        )
