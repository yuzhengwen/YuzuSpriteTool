"""A row of mutually exclusive toggle buttons (like a tab switch)."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget


class SegmentedControl(QWidget):
    changed = Signal(int)   # index of the chosen segment

    def __init__(self, labels: list[str], current: int = 0):
        super().__init__()
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        last = len(labels) - 1
        for i, text in enumerate(labels):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setObjectName("segmentFirst" if i == 0 else "segmentLast" if i == last else "segment")
            self._group.addButton(b, i)
            lay.addWidget(b)
        self._group.button(current).setChecked(True)
        self._group.idClicked.connect(self.changed)

    def current(self) -> int:
        return self._group.checkedId()

    def set_current(self, index: int) -> None:
        """Select a segment (emits `changed` if it differs)."""
        if index != self.current():
            self._group.button(index).setChecked(True)
            self.changed.emit(index)
