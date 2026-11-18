"""Zoomable, pannable pixel-art viewer with a checkerboard, cell overlays and file drop."""
from __future__ import annotations

import math
from typing import Iterable

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QGraphicsScene, QGraphicsView

from ...core import Rect
from .. import theme
from ..file_dialogs import dropped_image_paths
from ..qt_image import checker_brush
from .placeholder import paint_drop_placeholder

MIN_ZOOM = 0.02
MAX_ZOOM = 128.0
WHEEL_STEP = 1.25
CLICK_SLOP = 4   # pixels the mouse may move and still count as a click (not a pan)


class ImageView(QGraphicsView):
    filesDropped = Signal(list)                    # [path, ...]
    emptyClicked = Signal()                        # clicked while showing the placeholder
    sceneClicked = Signal(float, float, object)    # image x, y, keyboard modifiers

    def __init__(self, placeholder: str = "", accept_drops: bool = True):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.placeholder = placeholder
        self._pix_item = None
        self._grid_item = None
        self._highlight_item = None
        self._auto_fit = True
        self._press_pos = None

        self.setAcceptDrops(accept_drops)
        self.setRenderHint(QPainter.SmoothPixmapTransform, False)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setBackgroundBrush(theme.VIEW_BG)
        self.setFrameShape(QFrame.NoFrame)
        self.setMinimumSize(200, 160)
        # Pan by dragging and zoom with the wheel; scrollbars only add clutter.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    # ------------------------------------------------------------ content
    @property
    def has_image(self) -> bool:
        return self._pix_item is not None

    @property
    def auto_fit(self) -> bool:
        """True until the user zooms manually; the image then stays fitted on resize."""
        return self._auto_fit

    def set_pixmap(self, pm: QPixmap, fit: bool = True) -> None:
        """Show an image. With fit=False the current zoom/pan is kept (useful for live updates)."""
        keep = self.transform() if (not fit and self.has_image) else None
        self.scene().clear()
        self._grid_item = self._highlight_item = None
        self._pix_item = self.scene().addPixmap(pm)
        self._pix_item.setTransformationMode(Qt.FastTransformation)
        self.scene().setSceneRect(QRectF(pm.rect()))
        if keep is not None:
            self.setTransform(keep)
        else:
            self._auto_fit = True
            QTimer.singleShot(0, self.fit)   # after layout has given us our real size
        self.setCursor(Qt.OpenHandCursor)
        self.viewport().update()

    def update_pixmap(self, pm: QPixmap) -> None:
        """Swap the shown image cheaply, keeping zoom, pan and overlays (e.g. for animation).

        Falls back to set_pixmap when the size changes or nothing is shown yet.
        """
        if self.has_image and self._pix_item.pixmap().size() == pm.size():
            self._pix_item.setPixmap(pm)
        else:
            self.set_pixmap(pm, fit=not self.has_image or self._auto_fit)

    def clear_image(self) -> None:
        self.scene().clear()
        self._pix_item = self._grid_item = self._highlight_item = None
        self.resetTransform()
        self.unsetCursor()
        self.viewport().update()

    def set_grid(self, rects: Iterable[Rect]) -> None:
        """Outline cells (pass an empty list to hide)."""
        pen = QPen(theme.ACCENT, 1)
        pen.setCosmetic(True)   # stays 1 screen pixel at any zoom
        self._grid_item = self._replace_overlay(self._grid_item, rects, pen, QBrush(Qt.NoBrush), z=1)

    def set_highlight(self, rects: Iterable[Rect]) -> None:
        """Fill and outline selected cells (pass an empty list to clear)."""
        pen = QPen(theme.SELECTION, 2)
        pen.setCosmetic(True)
        fill = QColor(theme.SELECTION)
        fill.setAlpha(70)
        self._highlight_item = self._replace_overlay(self._highlight_item, rects, pen, QBrush(fill), z=2)

    def _replace_overlay(self, old, rects: Iterable[Rect], pen: QPen, brush: QBrush, z: int):
        if old is not None:
            self.scene().removeItem(old)
        rects = list(rects)
        if not self.has_image or not rects:
            return None
        path = QPainterPath()   # one path item draws thousands of cells cheaply
        for r in rects:
            path.addRect(r.x, r.y, r.w, r.h)
        item = self.scene().addPath(path, pen, brush)
        item.setZValue(z)
        return item

    # ------------------------------------------------------------ zoom
    def zoom(self) -> float:
        return self.transform().m11()

    def set_zoom(self, z: float) -> None:
        z = max(MIN_ZOOM, min(z, MAX_ZOOM))
        self.resetTransform()
        self.scale(z, z)
        self._auto_fit = False

    def zoom_by(self, factor: float) -> None:
        self.set_zoom(self.zoom() * factor)

    def fit(self) -> None:
        if not self.has_image:
            return
        # Fit the image's bounding box. fitInView(item) would fit the pixmap's *shape*,
        # which excludes transparent pixels and over-zooms sprites with empty edges.
        self.fitInView(self._pix_item.sceneBoundingRect(), Qt.KeepAspectRatio)
        z = self.zoom()
        if z > 1:   # whole-number zoom keeps pixels square and crisp
            self.resetTransform()
            self.scale(math.floor(z), math.floor(z))
        self._auto_fit = True

    def wheelEvent(self, e):
        if self.has_image:
            self.zoom_by(WHEEL_STEP ** (e.angleDelta().y() / 120))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._auto_fit:
            self.fit()

    # ------------------------------------------------------------ painting
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if self.has_image:
            # Checkerboard in screen space so squares stay the same size at any zoom.
            area = self.mapFromScene(self._pix_item.sceneBoundingRect()).boundingRect()
            painter.save()
            painter.resetTransform()
            painter.fillRect(area, checker_brush())
            painter.restore()

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        if not self.has_image and self.placeholder:
            painter.save()
            painter.resetTransform()
            paint_drop_placeholder(painter, self.viewport().rect(), self.placeholder, inset=24, font_scale=1.15)
            painter.restore()

    # ------------------------------------------------------------ mouse
    def mousePressEvent(self, e):
        self._press_pos = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if self._press_pos is None or e.button() != Qt.LeftButton:
            return
        moved = (e.position().toPoint() - self._press_pos).manhattanLength()
        self._press_pos = None
        if moved > CLICK_SLOP:
            return   # it was a pan
        if not self.has_image:
            self.emptyClicked.emit()
        else:
            p = self.mapToScene(e.position().toPoint())
            self.sceneClicked.emit(p.x(), p.y(), e.modifiers())

    # ------------------------------------------------------------ file drops
    def _accepts(self, e) -> bool:
        return self.acceptDrops() and e.mimeData().hasUrls()

    def dragEnterEvent(self, e):
        if self._accepts(e):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        self.dragEnterEvent(e)

    def dropEvent(self, e):
        paths = dropped_image_paths(e.mimeData().urls())
        if paths:
            e.acceptProposedAction()
            self.filesDropped.emit(paths)
