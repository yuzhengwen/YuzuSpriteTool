"""The dashed 'drop files here' box drawn inside empty views."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QPen

from .. import theme


def paint_drop_placeholder(painter: QPainter, area: QRect, text: str, *, inset: int = 20,
                           font_scale: float = 1.0) -> None:
    painter.save()
    box = area.adjusted(inset, inset, -inset, -inset)
    painter.setPen(QPen(theme.PLACEHOLDER_BORDER, 2, Qt.DashLine))
    painter.drawRoundedRect(box, 12, 12)
    painter.setPen(theme.PLACEHOLDER_TEXT)
    if font_scale != 1.0:
        font = painter.font()
        font.setPointSizeF(font.pointSizeF() * font_scale)
        painter.setFont(font)
    painter.drawText(box, Qt.AlignCenter | Qt.TextWordWrap, text)
    painter.restore()
