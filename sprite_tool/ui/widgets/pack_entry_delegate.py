"""Row painter for the Pack tab's sprite list: clickable thumbnail, Edit and revert buttons."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QToolTip

from .. import theme

# Item data roles the list items must provide.
ROLE_ENTRY_ID = Qt.UserRole + 1
ROLE_EDITED = Qt.UserRole + 2

BUTTON_H = 26
EDIT_W = 52
REVERT_W = 26
GAP = 6
RIGHT_PAD = 8
MIN_ROW_H = 52

EDIT_TIP = "Edit this sprite (crop / resize)"
REVERT_TIP = "Remove the edits and go back to the original image"
THUMB_TIP = "Click to open the sprite editor"

_BUTTON_EVENTS = (QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick)
_BUTTON_BG = QColor(58, 58, 64)
_BUTTON_BORDER = QColor(80, 80, 88)
_BUTTON_TEXT = QColor(225, 225, 230)
_REVERT_INK = QColor(255, 130, 130)


class PackEntryDelegate(QStyledItemDelegate):
    editRequested = Signal(int)       # row: Edit button or thumbnail clicked
    revertRequested = Signal(int)     # row: ✕ clicked

    # ------------------------------------------------------------ geometry
    @staticmethod
    def _revert_rect(row: QRect) -> QRect:
        return QRect(row.right() - RIGHT_PAD - REVERT_W, row.center().y() - BUTTON_H // 2, REVERT_W, BUTTON_H)

    @classmethod
    def _edit_rect(cls, row: QRect) -> QRect:
        r = cls._revert_rect(row)
        return QRect(r.left() - GAP - EDIT_W, r.top(), EDIT_W, BUTTON_H)

    def _view_option(self, option, index) -> QStyleOptionViewItem:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        return opt

    @staticmethod
    def _thumb_rect(opt: QStyleOptionViewItem) -> QRect:
        return opt.widget.style().subElementRect(QStyle.SE_ItemViewItemDecoration, opt, opt.widget)

    @staticmethod
    def _is_edited(index) -> bool:
        return bool(index.data(ROLE_EDITED))

    # ------------------------------------------------------------ painting
    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        return QSize(hint.width() + EDIT_W + REVERT_W + GAP + RIGHT_PAD, max(hint.height(), MIN_ROW_H))

    def paint(self, painter, option, index):
        opt = self._view_option(option, index)
        style = opt.widget.style()
        # Elide the label so it never runs under the buttons.
        text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, opt, opt.widget)
        room = self._edit_rect(opt.rect).left() - GAP - text_rect.left()
        opt.text = opt.fontMetrics.elidedText(opt.text, Qt.ElideRight, max(0, room))
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        edited = self._is_edited(index)
        if edited:
            self._paint_edited_dot(painter, self._thumb_rect(opt))
        self._paint_button(painter, self._edit_rect(opt.rect), "Edit")
        if edited:
            self._paint_revert(painter, self._revert_rect(opt.rect))
        painter.restore()

    @staticmethod
    def _paint_button(painter: QPainter, r: QRect, text: str) -> None:
        painter.setPen(QPen(_BUTTON_BORDER, 1))
        painter.setBrush(_BUTTON_BG)
        painter.drawRoundedRect(r.adjusted(0, 0, -1, -1), 6, 6)
        painter.setPen(_BUTTON_TEXT)
        painter.drawText(r, Qt.AlignCenter, text)

    @classmethod
    def _paint_revert(cls, painter: QPainter, r: QRect) -> None:
        cls._paint_button(painter, r, "")
        painter.setPen(QPen(_REVERT_INK, 2, Qt.SolidLine, Qt.RoundCap))
        m = 8
        painter.drawLine(r.left() + m, r.top() + m, r.right() - m, r.bottom() - m)
        painter.drawLine(r.right() - m, r.top() + m, r.left() + m, r.bottom() - m)

    @staticmethod
    def _paint_edited_dot(painter: QPainter, thumb: QRect) -> None:
        painter.setPen(QPen(theme.ICON_INK, 2))
        painter.setBrush(theme.ACCENT)
        painter.drawEllipse(thumb.right() - 9, thumb.top() - 1, 10, 10)

    # ------------------------------------------------------------ interaction
    def editorEvent(self, event, model, option, index):
        if event.type() not in _BUTTON_EVENTS or event.button() != Qt.LeftButton:
            return super().editorEvent(event, model, option, index)
        pos = event.position().toPoint()
        release = event.type() == QEvent.MouseButtonRelease

        if self._edit_rect(option.rect).contains(pos):
            if release:
                self.editRequested.emit(index.row())
            return True   # buttons swallow the click so selection/drag don't react
        if self._is_edited(index) and self._revert_rect(option.rect).contains(pos):
            if release:
                self.revertRequested.emit(index.row())
            return True
        # Plain click on the thumbnail opens the editor; the press still selects/drags as usual.
        if release and not event.modifiers() and self._thumb_rect(self._view_option(option, index)).contains(pos):
            self.editRequested.emit(index.row())
        return super().editorEvent(event, model, option, index)

    def helpEvent(self, event, view, option, index):
        if event.type() == QEvent.ToolTip:
            pos = event.pos()
            tip = None
            if self._edit_rect(option.rect).contains(pos):
                tip = EDIT_TIP
            elif self._is_edited(index) and self._revert_rect(option.rect).contains(pos):
                tip = REVERT_TIP
            elif self._thumb_rect(self._view_option(option, index)).contains(pos):
                tip = THUMB_TIP
            if tip:
                QToolTip.showText(event.globalPos(), tip, view)
                return True
        return super().helpEvent(event, view, option, index)
