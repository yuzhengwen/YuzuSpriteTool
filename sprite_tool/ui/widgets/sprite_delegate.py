"""Item delegate that adds a save button to the hovered sprite tile."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from .. import theme

BUTTON_SIZE = 24
BUTTON_MARGIN = 3
_MOUSE_EVENTS = (QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick)


class SpriteDelegate(QStyledItemDelegate):
    saveClicked = Signal(int)   # row

    @staticmethod
    def _button_rect(option) -> QRect:
        r = option.rect
        return QRect(r.right() - BUTTON_SIZE - BUTTON_MARGIN, r.top() + BUTTON_MARGIN, BUTTON_SIZE, BUTTON_SIZE)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if option.state & QStyle.State_MouseOver:
            self._paint_save_button(painter, self._button_rect(option))

    @staticmethod
    def _paint_save_button(painter: QPainter, b: QRect) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(theme.ACCENT)
        painter.drawRoundedRect(b, 6, 6)
        # Download glyph: arrow pointing at a tray line.
        painter.setPen(QPen(theme.ICON_INK, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cx = b.center().x() + 1
        tip = b.bottom() - 8
        painter.drawLine(cx, b.top() + 6, cx, tip)
        painter.drawLine(cx - 4, tip - 4, cx, tip)
        painter.drawLine(cx + 4, tip - 4, cx, tip)
        painter.drawLine(b.left() + 7, b.bottom() - 5, b.right() - 5, b.bottom() - 5)
        painter.restore()

    def editorEvent(self, event, model, option, index):
        # Swallow clicks on the button so they don't change the selection.
        if event.type() in _MOUSE_EVENTS and self._button_rect(option).contains(event.position().toPoint()):
            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self.saveClicked.emit(index.row())
            return True
        return super().editorEvent(event, model, option, index)
