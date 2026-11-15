"""List that the user reorders by dragging, and that accepts image files from outside."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QAbstractItemView, QListWidget

from ..file_dialogs import dropped_image_paths
from .placeholder import paint_drop_placeholder

ICON_SIZE = 44
EMPTY_TEXT = "Drop sprite images (or a folder) here\nor click “Add sprites…”"


class SpriteOrderList(QListWidget):
    filesDropped = Signal(list)   # image paths dropped from outside
    reordered = Signal()          # the user dragged items to a new position
    openRequested = Signal()      # double-clicked while empty

    def __init__(self):
        super().__init__()
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setAcceptDrops(True)
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setSpacing(2)

    # External file drops are handled here; internal moves go to QListWidget.
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            paths = dropped_image_paths(e.mimeData().urls())
            if paths:
                self.filesDropped.emit(paths)
            return
        super().dropEvent(e)
        QTimer.singleShot(0, self.reordered.emit)   # after Qt finishes moving the rows

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.count() == 0:
            p = QPainter(self.viewport())
            paint_drop_placeholder(p, self.viewport().rect(), EMPTY_TEXT, inset=16)
            p.end()

    def mouseDoubleClickEvent(self, e):
        if self.count() == 0:
            self.openRequested.emit()
            return
        super().mouseDoubleClickEvent(e)
