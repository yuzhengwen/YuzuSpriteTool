"""Image view where dragging with the left button draws a crop rectangle."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsView

from ...core import Rect
from .. import theme
from .image_view import ImageView

DIM_OUTSIDE = QColor(0, 0, 0, 150)   # darkens everything outside the crop area


class CropView(ImageView):
    """Left-drag: draw a crop area. Right- or middle-drag: pan. Wheel: zoom."""

    cropDrawn = Signal(object)   # Rect, emitted live while dragging

    def __init__(self):
        super().__init__(accept_drops=False)
        self.setDragMode(QGraphicsView.NoDrag)   # left button draws instead of panning
        self._crop_items = []
        self._drag_origin: QPointF | None = None
        self._pan_last = None

    def set_pixmap(self, pm: QPixmap, fit: bool = True) -> None:
        super().set_pixmap(pm, fit)
        self._crop_items = []   # the scene was cleared
        self.viewport().setCursor(Qt.CrossCursor)

    # ------------------------------------------------------------ overlay
    def set_crop(self, rect: Rect | None) -> None:
        """Show `rect` as the kept area (None hides the overlay)."""
        for item in self._crop_items:
            self.scene().removeItem(item)
        self._crop_items = []
        if not self.has_image or rect is None:
            return
        image = QPainterPath()
        image.addRect(self._pix_item.boundingRect())
        kept = QPainterPath()
        kept.addRect(QRectF(rect.x, rect.y, rect.w, rect.h))
        dim = self.scene().addPath(image.subtracted(kept), QPen(Qt.NoPen), QBrush(DIM_OUTSIDE))
        pen = QPen(theme.ACCENT, 2)
        pen.setCosmetic(True)
        outline = self.scene().addRect(QRectF(rect.x, rect.y, rect.w, rect.h), pen)
        for z, item in enumerate((dim, outline), start=3):
            item.setZValue(z)
        self._crop_items = [dim, outline]

    # ------------------------------------------------------------ mouse
    def _rect_between(self, a: QPointF, b: QPointF) -> Rect | None:
        """Whole-pixel rectangle spanning two scene points, clamped to the image."""
        img_w = int(self._pix_item.boundingRect().width())
        img_h = int(self._pix_item.boundingRect().height())
        left = max(0, min(img_w, math.floor(min(a.x(), b.x()))))
        top = max(0, min(img_h, math.floor(min(a.y(), b.y()))))
        right = max(0, min(img_w, math.ceil(max(a.x(), b.x()))))
        bottom = max(0, min(img_h, math.ceil(max(a.y(), b.y()))))
        if right - left < 1 or bottom - top < 1:
            return None
        return Rect(left, top, right - left, bottom - top)

    def mousePressEvent(self, e):
        if not self.has_image:
            return super().mousePressEvent(e)
        if e.button() == Qt.LeftButton:
            self._drag_origin = self.mapToScene(e.position().toPoint())
        elif e.button() in (Qt.RightButton, Qt.MiddleButton):
            self._pan_last = e.position().toPoint()
            self.viewport().setCursor(Qt.ClosedHandCursor)
        e.accept()

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if self._drag_origin is not None:
            rect = self._rect_between(self._drag_origin, self.mapToScene(pos))
            if rect is not None:
                self.cropDrawn.emit(rect)
        elif self._pan_last is not None:
            delta = pos - self._pan_last
            self._pan_last = pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_origin = None
        if self._pan_last is not None:
            self._pan_last = None
            self.viewport().setCursor(Qt.CrossCursor)
        e.accept()

    def mouseDoubleClickEvent(self, e):
        e.accept()   # a double-click shouldn't start a zero-size crop
