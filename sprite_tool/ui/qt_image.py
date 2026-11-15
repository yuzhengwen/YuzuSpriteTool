"""Converting Pillow images for Qt, plus thumbnail and checkerboard rendering."""
from __future__ import annotations

import math

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QGuiApplication, QIcon, QImage, QPainter, QPixmap

from . import theme

CHECKER_SQUARE = 8

_checker: QBrush | None = None


def pil_to_qimage(img: Image.Image) -> QImage:
    img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    # .copy() detaches the QImage from the Python bytes buffer.
    return QImage(data, img.width, img.height, img.width * 4, QImage.Format_RGBA8888).copy()


def pil_to_pixmap(img: Image.Image) -> QPixmap:
    return QPixmap.fromImage(pil_to_qimage(img))


def copy_to_clipboard(img: Image.Image) -> None:
    QGuiApplication.clipboard().setImage(pil_to_qimage(img))


def checker_brush() -> QBrush:
    """Shared checkerboard brush that shows transparency (created on first use)."""
    global _checker
    if _checker is None:
        s = CHECKER_SQUARE
        pm = QPixmap(s * 2, s * 2)
        pm.fill(theme.CHECKER_LIGHT)
        p = QPainter(pm)
        p.fillRect(0, 0, s, s, theme.CHECKER_DARK)
        p.fillRect(s, s, s, s, theme.CHECKER_DARK)
        p.end()
        _checker = QBrush(pm)
    return _checker


def thumb_pixmap(pm: QPixmap, box: int) -> QPixmap:
    """Fit a sprite in a box x box tile over a checkerboard.

    Upscaling uses whole-number factors and nearest-neighbour so pixel art stays crisp.
    """
    w, h = max(1, pm.width()), max(1, pm.height())
    f = min(box / w, box / h)
    if f >= 1:
        f = math.floor(f)
    tw, th = max(1, round(w * f)), max(1, round(h * f))
    mode = Qt.FastTransformation if f >= 1 else Qt.SmoothTransformation
    scaled = pm.scaled(tw, th, Qt.IgnoreAspectRatio, mode)

    out = QPixmap(box, box)
    out.fill(Qt.transparent)
    p = QPainter(out)
    x, y = (box - tw) // 2, (box - th) // 2
    p.fillRect(x, y, tw, th, checker_brush())
    p.drawPixmap(x, y, scaled)
    p.end()
    return out


def sprite_icon(pm: QPixmap) -> QIcon:
    """Icon that looks the same when selected (Qt tints selected icons blue by default)."""
    icon = QIcon(pm)
    icon.addPixmap(pm, QIcon.Selected)
    return icon
