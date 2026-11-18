"""Horizontal filmstrip of animation frames that highlights the current one."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QAbstractItemView, QListView, QListWidget, QListWidgetItem

from ..qt_image import sprite_icon, thumb_pixmap

THUMB = 64
TILE_W, TILE_H = THUMB + 16, THUMB + 30


class FrameStrip(QListWidget):
    frameChosen = Signal(int)      # user picked a frame (click or arrow keys)
    frameActivated = Signal(int)   # user double-clicked a frame (play from here)

    def __init__(self):
        super().__init__()
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(False)
        self.setMovement(QListView.Static)
        self.setResizeMode(QListView.Adjust)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setUniformItemSizes(True)
        self.setIconSize(QSize(THUMB, THUMB))
        self.setGridSize(QSize(TILE_W, TILE_H))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedHeight(TILE_H + 26)   # room for the horizontal scrollbar
        self._programmatic = False

        self.currentRowChanged.connect(self._on_current_changed)
        self.itemDoubleClicked.connect(lambda item: self.frameActivated.emit(self.row(item)))

    def set_frames(self, frames: list[QPixmap]) -> None:
        self._programmatic = True
        self.clear()
        for i, pm in enumerate(frames):
            item = QListWidgetItem(sprite_icon(thumb_pixmap(pm, THUMB)), str(i + 1))
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.addItem(item)
        self._programmatic = False

    def set_current(self, index: int) -> None:
        """Highlight a frame without reporting it as a user choice."""
        if index == self.currentRow() or not 0 <= index < self.count():
            return
        self._programmatic = True
        self.setCurrentRow(index)
        self.scrollToItem(self.item(index), QAbstractItemView.EnsureVisible)
        self._programmatic = False

    def _on_current_changed(self, row: int) -> None:
        if not self._programmatic and row >= 0:
            self.frameChosen.emit(row)
