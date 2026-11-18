"""Media-control icons drawn in code, so they look the same with any system font.

(Glyphs like ⏮ ⏭ are swapped for colored emoji on Windows.)
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF

from .. import theme

FIRST, PREVIOUS, PLAY, PAUSE, NEXT, LAST = "first", "previous", "play", "pause", "next", "last"
CANVAS = 32                                  # drawn large, shown at icon size, so edges stay smooth
INK = QColor(225, 225, 230)                  # normal state
INK_ON = theme.ICON_INK                      # on an accent-colored (checked) button


def _triangle(p: QPainter, left: float, top: float, right: float, bottom: float) -> None:
    mid = (top + bottom) / 2
    p.drawPolygon(QPolygonF([QPointF(left, top), QPointF(right, mid), QPointF(left, bottom)]))


def _draw(p: QPainter, kind: str) -> None:
    """Shapes for the forward-facing variants; backward ones are drawn mirrored."""
    if kind == PLAY:
        _triangle(p, 10, 7, 25, 25)
    elif kind == PAUSE:
        p.drawRect(QRectF(9, 7, 5, 18))
        p.drawRect(QRectF(18, 7, 5, 18))
    elif kind in (NEXT, PREVIOUS):        # one triangle + bar: step one frame
        _triangle(p, 9, 9, 20, 23)
        p.drawRect(QRectF(21, 9, 3, 14))
    elif kind in (LAST, FIRST):           # two triangles + bar: jump to the end
        _triangle(p, 5, 9, 14, 23)
        _triangle(p, 13, 9, 22, 23)
        p.drawRect(QRectF(23, 9, 3, 14))


def _pixmap(kind: str, color: QColor) -> QPixmap:
    pm = QPixmap(CANVAS, CANVAS)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    if kind in (PREVIOUS, FIRST):
        p.translate(CANVAS, 0)
        p.scale(-1, 1)
    _draw(p, kind)
    p.end()
    return pm


def transport_icon(kind: str) -> QIcon:
    icon = QIcon()
    icon.addPixmap(_pixmap(kind, INK), QIcon.Normal, QIcon.Off)
    icon.addPixmap(_pixmap(kind, INK_ON), QIcon.Normal, QIcon.On)   # checked (playing) state
    return icon
