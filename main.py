"""Yuzu Sprite Tool - a local desktop app for slicing and packing sprite sheets.

Run with run.bat, or:  .venv\\Scripts\\python.exe main.py
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QEvent, QItemSelectionModel, QRect, QRectF, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction, QBrush, QColor, QGuiApplication, QIcon, QImage, QKeySequence, QPainter,
    QPainterPath, QPalette, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QColorDialog, QComboBox,
    QDialog, QFileDialog, QFrame, QGraphicsScene, QGraphicsView, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMessageBox, QPushButton, QRadioButton, QSizePolicy, QSlider, QSpinBox,
    QSplitter, QStyle, QStyledItemDelegate, QTabWidget, QVBoxLayout, QWidget,
)

import sprite_core as core

APP_NAME = "Yuzu Sprite Tool"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tga", ".tif", ".tiff"}
IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tga *.tif *.tiff);;All files (*)"
ROLE_ID = Qt.UserRole + 1

ACCENT = QColor(255, 176, 46)        # yuzu orange: grid lines
SELECT = QColor(90, 170, 255)        # selected cells


# ====================================================================== helpers

def pil_to_qimage(img: Image.Image) -> QImage:
    img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    return QImage(data, img.width, img.height, img.width * 4, QImage.Format_RGBA8888).copy()


def pil_to_pixmap(img: Image.Image) -> QPixmap:
    return QPixmap.fromImage(pil_to_qimage(img))


_checker: QBrush | None = None


def checker_brush() -> QBrush:
    global _checker
    if _checker is None:
        s = 8
        pm = QPixmap(s * 2, s * 2)
        pm.fill(QColor(58, 58, 62))
        p = QPainter(pm)
        p.fillRect(0, 0, s, s, QColor(44, 44, 48))
        p.fillRect(s, s, s, s, QColor(44, 44, 48))
        p.end()
        _checker = QBrush(pm)
    return _checker


def thumb_pixmap(pm: QPixmap, box: int) -> QPixmap:
    """Fit a sprite in a box x box tile. Upscales by whole numbers so pixel art stays crisp."""
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


def make_icon(pm: QPixmap) -> QIcon:
    icon = QIcon(pm)
    icon.addPixmap(pm, QIcon.Selected)  # no blue tint over selected sprites
    return icon


def image_paths(urls) -> list[str]:
    out = []
    for u in urls:
        if u.isLocalFile():
            p = Path(u.toLocalFile())
            if p.is_dir():
                out += sorted(str(c) for c in p.iterdir() if c.suffix.lower() in IMAGE_EXTS)
            elif p.suffix.lower() in IMAGE_EXTS:
                out.append(str(p))
    return out


def spin(lo: int, hi: int, value: int, special: str | None = None, suffix: str = " px") -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(lo, hi)
    sb.setValue(value)
    sb.setSuffix(suffix)
    sb.setAccelerated(True)
    if special:
        sb.setSpecialValueText(special)
    return sb


def settings() -> QSettings:
    return QSettings("Yuzu", "SpriteTool")


def last_dir() -> str:
    return settings().value("lastDir", str(Path.home()))


def remember_dir(path: str) -> None:
    p = Path(path)
    settings().setValue("lastDir", str(p if p.is_dir() else p.parent))


def hint(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("hint")
    lbl.setWordWrap(True)
    return lbl


# ====================================================================== image view

class ImageView(QGraphicsView):
    """Zoomable, pannable pixel-art viewer with a checkerboard, grid overlay and file drop."""

    filesDropped = Signal(list)
    emptyClicked = Signal()
    sceneClicked = Signal(float, float, object)   # x, y, keyboard modifiers

    def __init__(self, placeholder: str = "", accept_drops: bool = True):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.placeholder = placeholder
        self._pix_item = None
        self._grid_item = None
        self._hl_item = None
        self._auto_fit = True
        self._press = None
        self.setAcceptDrops(accept_drops)
        self.setRenderHint(QPainter.SmoothPixmapTransform, False)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setBackgroundBrush(QColor(30, 30, 33))
        self.setFrameShape(QFrame.NoFrame)
        self.setMinimumSize(200, 160)
        # Pan by dragging and zoom with the wheel; scrollbars only add clutter.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    # -- content
    def has_image(self) -> bool:
        return self._pix_item is not None

    def set_pixmap(self, pm: QPixmap, fit: bool = True) -> None:
        keep = self.transform() if not fit and self._pix_item else None
        self.scene().clear()
        self._grid_item = self._hl_item = None
        self._pix_item = self.scene().addPixmap(pm)
        self._pix_item.setTransformationMode(Qt.FastTransformation)
        self.scene().setSceneRect(QRectF(pm.rect()))
        if keep is not None:
            self.setTransform(keep)
        else:
            self._auto_fit = True
            QTimer.singleShot(0, self.fit)
        self.setCursor(Qt.OpenHandCursor)
        self.viewport().update()

    def clear_image(self) -> None:
        self.scene().clear()
        self._pix_item = self._grid_item = self._hl_item = None
        self.resetTransform()
        self.unsetCursor()
        self.viewport().update()

    def _rect_path(self, rects) -> QPainterPath:
        path = QPainterPath()
        for r in rects:
            path.addRect(r.x, r.y, r.w, r.h)
        return path

    def set_grid(self, rects) -> None:
        if self._grid_item is not None:
            self.scene().removeItem(self._grid_item)
            self._grid_item = None
        if self._pix_item is None or not rects:
            return
        pen = QPen(ACCENT, 1)
        pen.setCosmetic(True)
        self._grid_item = self.scene().addPath(self._rect_path(rects), pen)
        self._grid_item.setZValue(1)

    def set_highlight(self, rects) -> None:
        if self._hl_item is not None:
            self.scene().removeItem(self._hl_item)
            self._hl_item = None
        if self._pix_item is None or not rects:
            return
        pen = QPen(SELECT, 2)
        pen.setCosmetic(True)
        fill = QColor(SELECT)
        fill.setAlpha(70)
        self._hl_item = self.scene().addPath(self._rect_path(rects), pen, QBrush(fill))
        self._hl_item.setZValue(2)

    # -- zoom
    def zoom(self) -> float:
        return self.transform().m11()

    def set_zoom(self, z: float) -> None:
        z = max(0.02, min(z, 128.0))
        self.resetTransform()
        self.scale(z, z)
        self._auto_fit = False

    def zoom_by(self, factor: float) -> None:
        self.set_zoom(self.zoom() * factor)

    def fit(self) -> None:
        if self._pix_item is None:
            return
        self.fitInView(self._pix_item, Qt.KeepAspectRatio)
        z = self.zoom()
        if z > 1:  # snap to a whole-number zoom for crisp pixels
            self.resetTransform()
            self.scale(math.floor(z), math.floor(z))
        self._auto_fit = True

    def wheelEvent(self, e):
        if self._pix_item is None:
            return
        steps = e.angleDelta().y() / 120
        self.zoom_by(1.25 ** steps)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._auto_fit:
            self.fit()

    # -- painting
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if self._pix_item is not None:
            r = self.mapFromScene(self._pix_item.sceneBoundingRect()).boundingRect()
            painter.save()
            painter.resetTransform()
            painter.fillRect(r, checker_brush())
            painter.restore()

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        if self._pix_item is None and self.placeholder:
            painter.save()
            painter.resetTransform()
            vr = self.viewport().rect().adjusted(24, 24, -24, -24)
            pen = QPen(QColor(110, 110, 118), 2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRoundedRect(vr, 12, 12)
            painter.setPen(QColor(160, 160, 168))
            f = painter.font()
            f.setPointSizeF(f.pointSizeF() * 1.15)
            painter.setFont(f)
            painter.drawText(vr, Qt.AlignCenter | Qt.TextWordWrap, self.placeholder)
            painter.restore()

    # -- mouse
    def mousePressEvent(self, e):
        self._press = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if self._press is None or e.button() != Qt.LeftButton:
            return
        moved = (e.position().toPoint() - self._press).manhattanLength()
        self._press = None
        if moved > 4:
            return
        if self._pix_item is None:
            self.emptyClicked.emit()
        else:
            sp = self.mapToScene(e.position().toPoint())
            self.sceneClicked.emit(sp.x(), sp.y(), e.modifiers())

    # -- drag & drop of files
    def dragEnterEvent(self, e):
        if self.acceptDrops() and e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self.acceptDrops() and e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        paths = image_paths(e.mimeData().urls())
        if paths:
            e.acceptProposedAction()
            self.filesDropped.emit(paths)


class ZoomBar(QWidget):
    """Fit / 1:1 / - / + buttons for an ImageView."""

    def __init__(self, view: ImageView):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        for text, tip, fn in (
            ("Fit", "Fit to view", view.fit),
            ("1:1", "Actual pixels", lambda: view.set_zoom(1)),
            ("−", "Zoom out", lambda: view.zoom_by(1 / 1.5)),
            ("+", "Zoom in", lambda: view.zoom_by(1.5)),
        ):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFixedWidth(40 if len(text) > 1 else 30)
            b.clicked.connect(fn)
            lay.addWidget(b)


# ====================================================================== preview popup

class PreviewDialog(QDialog):
    def __init__(self, parent, img: Image.Image, name: str, on_save):
        super().__init__(parent)
        self.setWindowTitle(f"{name}  ({img.width} × {img.height} px)")
        self.img = img
        pm = pil_to_pixmap(img)

        self.view = ImageView(accept_drops=False)
        self.view.set_pixmap(pm, fit=True)  # fits (whole-number zoom) and refits on resize

        info = QLabel(f"<b>{name}</b> &nbsp; {img.width} × {img.height} px &nbsp;·&nbsp; scroll to zoom, drag to pan")
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setImage(pil_to_qimage(img)))
        save_btn = QPushButton("Save PNG…")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(on_save)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)

        bottom = QHBoxLayout()
        bottom.addWidget(ZoomBar(self.view))
        bottom.addStretch()
        bottom.addWidget(copy_btn)
        bottom.addWidget(save_btn)
        bottom.addWidget(close_btn)

        lay = QVBoxLayout(self)
        lay.addWidget(info)
        lay.addWidget(self.view, 1)
        lay.addLayout(bottom)

        screen = self.screen().availableGeometry()
        target = min(screen.width(), screen.height()) * 0.7
        z = target / max(img.width, img.height)
        if z >= 1:
            z = math.floor(z)
        w = int(min(max(img.width * z + 60, 460), screen.width() * 0.9))
        h = int(min(max(img.height * z + 130, 340), screen.height() * 0.9))
        self.resize(w, h)


# ====================================================================== sprite tile delegate

class SpriteDelegate(QStyledItemDelegate):
    """Draws a small save button on the hovered sprite tile."""

    saveClicked = Signal(int)

    BTN = 24

    def _btn_rect(self, option) -> QRect:
        r = option.rect
        return QRect(r.right() - self.BTN - 3, r.top() + 3, self.BTN, self.BTN)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if option.state & QStyle.State_MouseOver:
            b = self._btn_rect(option)
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(ACCENT))
            painter.drawRoundedRect(b, 6, 6)
            pen = QPen(QColor(30, 30, 33), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            cx = b.center().x() + 1
            painter.drawLine(cx, b.top() + 6, cx, b.bottom() - 8)
            painter.drawLine(cx - 4, b.bottom() - 12, cx, b.bottom() - 8)
            painter.drawLine(cx + 4, b.bottom() - 12, cx, b.bottom() - 8)
            painter.drawLine(b.left() + 7, b.bottom() - 5, b.right() - 5, b.bottom() - 5)
            painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick):
            if self._btn_rect(option).contains(event.position().toPoint()):
                if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                    self.saveClicked.emit(index.row())
                return True
        return super().editorEvent(event, model, option, index)


# ====================================================================== unpack tab

class UnpackTab(QWidget):
    status = Signal(str)
    sendToPack = Signal(list)   # [(name, PIL image)]

    def __init__(self):
        super().__init__()
        self.sheet: Image.Image | None = None
        self.sheet_path: str | None = None
        self.cells: list[core.Rect] = []
        self.sprites: list[core.Sprite] = []
        self.pixmaps: list[QPixmap] = []

        self._timer = QTimer(self, singleShot=True, interval=120)
        self._timer.timeout.connect(self.reslice)
        self._thumb_timer = QTimer(self, singleShot=True, interval=80)
        self._thumb_timer.timeout.connect(self._rebuild_icons)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([700, 600])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(splitter)
        self._update_mode()

    # ---------------------------------------------------------------- layout
    def _build_left(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)

        top = QHBoxLayout()
        title = QLabel("Sprite sheet")
        title.setObjectName("paneTitle")
        open_btn = QPushButton("Open sheet…")
        open_btn.setObjectName("primary")
        open_btn.clicked.connect(self.open_dialog)
        self.view = ImageView("Drop a sprite sheet here\nor click to choose a file")
        self.view.filesDropped.connect(lambda paths: self.load_sheet(paths[0]))
        self.view.emptyClicked.connect(self.open_dialog)
        self.view.sceneClicked.connect(self._on_sheet_clicked)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(ZoomBar(self.view))
        top.addWidget(open_btn)
        lay.addLayout(top)

        self.file_label = QLabel("No sheet loaded")
        self.file_label.setObjectName("hint")
        lay.addWidget(self.file_label)
        lay.addWidget(self.view, 1)

        box = QGroupBox("How to slice")
        g = QGridLayout(box)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(6)

        self.rb_size = QRadioButton("Fixed cell size")
        self.rb_grid = QRadioButton("Columns × rows")
        self.rb_size.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.rb_size)
        grp.addButton(self.rb_grid)
        self.rb_size.toggled.connect(self._update_mode)

        self.sp_w = spin(1, 16384, 32)
        self.sp_h = spin(1, 16384, 32)
        self.sp_cols = spin(1, 1000, 4, suffix="")
        self.sp_rows = spin(1, 1000, 4, suffix="")
        self.sp_ox = spin(0, 16384, 0)
        self.sp_oy = spin(0, 16384, 0)
        self.sp_sx = spin(0, 16384, 0)
        self.sp_sy = spin(0, 16384, 0)
        self.cb_corner = QComboBox()
        for label, key in (("Top-left", "tl"), ("Top-right", "tr"), ("Bottom-left", "bl"), ("Bottom-right", "br")):
            self.cb_corner.addItem(label, key)
        self.ck_partial = QCheckBox("Keep cut-off edge cells")
        self.ck_partial.setToolTip("Fixed cell size only: keep cells at the right/bottom edge that are smaller than a full cell.")
        self.ck_skip = QCheckBox("Skip empty cells")
        self.ck_skip.setChecked(True)
        self.ck_skip.setToolTip("Drop cells that are fully transparent.")
        self.ck_trim = QCheckBox("Trim transparent edges")
        self.ck_trim.setToolTip("Crop each sprite to its visible pixels.")

        g.addWidget(self.rb_size, 0, 0, 1, 2)
        g.addWidget(self.rb_grid, 0, 2, 1, 2)
        g.addWidget(QLabel("Width"), 1, 0)
        g.addWidget(self.sp_w, 1, 1)
        g.addWidget(QLabel("Columns"), 1, 2)
        g.addWidget(self.sp_cols, 1, 3)
        g.addWidget(QLabel("Height"), 2, 0)
        g.addWidget(self.sp_h, 2, 1)
        g.addWidget(QLabel("Rows"), 2, 2)
        g.addWidget(self.sp_rows, 2, 3)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("sep")
        g.addWidget(sep, 3, 0, 1, 4)

        g.addWidget(QLabel("Start from"), 4, 0)
        g.addWidget(self.cb_corner, 4, 1)
        g.addWidget(QLabel("Offset X"), 5, 0)
        g.addWidget(self.sp_ox, 5, 1)
        g.addWidget(QLabel("Offset Y"), 5, 2)
        g.addWidget(self.sp_oy, 5, 3)
        g.addWidget(QLabel("Gap X"), 6, 0)
        g.addWidget(self.sp_sx, 6, 1)
        g.addWidget(QLabel("Gap Y"), 6, 2)
        g.addWidget(self.sp_sy, 6, 3)
        g.addWidget(self.ck_skip, 7, 0, 1, 2)
        g.addWidget(self.ck_trim, 7, 2, 1, 2)
        g.addWidget(self.ck_partial, 8, 0, 1, 4)
        for col in (1, 3):
            g.setColumnStretch(col, 1)
        for wdg in (self.sp_ox, self.sp_oy, self.sp_sx, self.sp_sy):
            wdg.setToolTip("Offset: where cutting starts, measured from the start corner.\nGap: empty space between cells.")

        for sb in (self.sp_w, self.sp_h, self.sp_cols, self.sp_rows, self.sp_ox, self.sp_oy, self.sp_sx, self.sp_sy):
            sb.valueChanged.connect(self._schedule)
        for ck in (self.ck_partial, self.ck_skip, self.ck_trim):
            ck.toggled.connect(self._schedule)
        self.cb_corner.currentIndexChanged.connect(self._schedule)
        self.rb_size.toggled.connect(self._schedule)

        lay.addWidget(box)
        self.slice_info = QLabel("")
        self.slice_info.setObjectName("hint")
        lay.addWidget(self.slice_info)
        return w

    def _build_right(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 0, 0, 0)

        top = QHBoxLayout()
        title = QLabel("Sliced sprites")
        title.setObjectName("paneTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("hint")
        sel_all = QPushButton("Select all")
        sel_all.clicked.connect(lambda: self.list.selectAll())
        sel_none = QPushButton("Select none")
        sel_none.clicked.connect(lambda: self.list.clearSelection())
        top.addWidget(title)
        top.addWidget(self.count_label)
        top.addStretch()
        top.addWidget(sel_all)
        top.addWidget(sel_none)
        lay.addLayout(top)

        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setUniformItemSizes(True)
        self.list.setSpacing(4)
        self.list.setMouseTracking(True)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        self.list.itemDoubleClicked.connect(lambda it: self.preview(self.list.row(it)))
        self.list.itemSelectionChanged.connect(self._sync_highlight)
        self.delegate = SpriteDelegate(self.list)
        self.delegate.saveClicked.connect(self.save_one)
        self.list.setItemDelegate(self.delegate)
        lay.addWidget(self.list, 1)

        size_row = QHBoxLayout()
        size_row.addWidget(hint("Double-click to preview · hover for the save button · Ctrl/Shift-click to pick several"), 1)
        size_row.addWidget(QLabel("Thumb size"))
        self.thumb_slider = QSlider(Qt.Horizontal)
        self.thumb_slider.setRange(32, 256)
        self.thumb_slider.setValue(96)
        self.thumb_slider.setFixedWidth(140)
        self.thumb_slider.valueChanged.connect(lambda: self._thumb_timer.start())
        size_row.addWidget(self.thumb_slider)
        lay.addLayout(size_row)

        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("File name prefix"))
        self.prefix = QLineEdit("sprite")
        self.prefix.setMaximumWidth(180)
        self.prefix.textChanged.connect(self._rename_items)
        bottom.addWidget(self.prefix)
        bottom.addStretch()
        self.send_btn = QPushButton("Send to Pack tab")
        self.send_btn.setToolTip("Copy the selected sprites (or all, if none are selected) into the Pack tab.")
        self.send_btn.clicked.connect(self._send_to_pack)
        self.save_sel_btn = QPushButton("Save selected…")
        self.save_sel_btn.clicked.connect(self.save_selected)
        self.save_all_btn = QPushButton("Save all…")
        self.save_all_btn.setObjectName("primary")
        self.save_all_btn.clicked.connect(lambda: self.save_many(list(range(len(self.sprites)))))
        bottom.addWidget(self.send_btn)
        bottom.addWidget(self.save_sel_btn)
        bottom.addWidget(self.save_all_btn)
        lay.addLayout(bottom)

        save_sc = QAction(self)
        save_sc.setShortcut(QKeySequence.Save)
        save_sc.triggered.connect(self.save_selected)
        self.addAction(save_sc)
        self._update_buttons()
        return w

    # ---------------------------------------------------------------- settings
    def slice_settings(self) -> core.SliceSettings:
        return core.SliceSettings(
            mode="size" if self.rb_size.isChecked() else "grid",
            cell_w=self.sp_w.value(), cell_h=self.sp_h.value(),
            cols=self.sp_cols.value(), rows=self.sp_rows.value(),
            offset_x=self.sp_ox.value(), offset_y=self.sp_oy.value(),
            spacing_x=self.sp_sx.value(), spacing_y=self.sp_sy.value(),
            corner=self.cb_corner.currentData(),
            include_partial=self.ck_partial.isChecked(),
            skip_empty=self.ck_skip.isChecked(),
            trim=self.ck_trim.isChecked(),
        )

    def _update_mode(self):
        size = self.rb_size.isChecked()
        for wdg in (self.sp_w, self.sp_h, self.ck_partial):
            wdg.setEnabled(size)
        for wdg in (self.sp_cols, self.sp_rows):
            wdg.setEnabled(not size)

    def _schedule(self):
        if self.sheet is not None:
            self._timer.start()

    # ---------------------------------------------------------------- loading
    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open sprite sheet", last_dir(), IMAGE_FILTER)
        if path:
            self.load_sheet(path)

    def load_sheet(self, path: str):
        try:
            img = core.load_rgba(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, APP_NAME, f"Could not open the image:\n{path}\n\n{exc}")
            return
        remember_dir(path)
        self.sheet, self.sheet_path = img, path
        self.view.set_pixmap(pil_to_pixmap(img))
        self.file_label.setText(f"{Path(path).name}  ·  {img.width} × {img.height} px")
        self.prefix.blockSignals(True)
        self.prefix.setText(Path(path).stem)
        self.prefix.blockSignals(False)
        self.reslice()
        self.status.emit(f"Opened {path}")

    # ---------------------------------------------------------------- slicing
    def reslice(self):
        if self.sheet is None:
            return
        try:
            cells, sprites = core.slice_sheet(self.sheet, self.slice_settings())
        except ValueError as exc:
            self.slice_info.setText(f"<span style='color:#ff7a7a'>{exc}</span>")
            return
        self.cells, self.sprites = cells, sprites
        self.pixmaps = [pil_to_pixmap(s.image) for s in sprites]
        self.view.set_grid(cells)
        self.view.set_highlight([])
        self._populate()
        skipped = len(cells) - len(sprites)
        extra = f" · {skipped} empty skipped" if skipped else ""
        if cells:
            c0 = cells[0]
            self.slice_info.setText(f"{len(cells)} cells of {c0.w} × {c0.h} px{extra}")
        else:
            self.slice_info.setText("<span style='color:#ff7a7a'>No cells fit. Check the size, offset and gap.</span>")

    def name_for(self, i: int) -> str:
        prefix = self.prefix.text().strip() or "sprite"
        digits = max(2, len(str(max(0, len(self.sprites) - 1))))
        return f"{prefix}_{i:0{digits}d}"

    def _populate(self):
        self.list.blockSignals(True)
        self.list.clear()
        box = self.thumb_slider.value()
        self.list.setIconSize(QSize(box, box))
        self.list.setGridSize(QSize(box + 26, box + 46))
        for i, (s, pm) in enumerate(zip(self.sprites, self.pixmaps)):
            it = QListWidgetItem(make_icon(thumb_pixmap(pm, box)), self._label(i))
            it.setToolTip(f"{self.name_for(i)}\n{s.image.width} × {s.image.height} px\nfrom x={s.cell.x}, y={s.cell.y}")
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.list.addItem(it)
        self.list.blockSignals(False)
        self.count_label.setText(f"{len(self.sprites)} sprites" if self.sprites else "")
        self._update_buttons()

    def _label(self, i: int) -> str:
        s = self.sprites[i]
        return f"{self.name_for(i)}\n{s.image.width}×{s.image.height}"

    def _rename_items(self):
        for i in range(self.list.count()):
            self.list.item(i).setText(self._label(i))

    def _rebuild_icons(self):
        box = self.thumb_slider.value()
        self.list.setIconSize(QSize(box, box))
        self.list.setGridSize(QSize(box + 26, box + 46))
        for i, pm in enumerate(self.pixmaps):
            self.list.item(i).setIcon(make_icon(thumb_pixmap(pm, box)))

    def selected_rows(self) -> list[int]:
        return sorted(self.list.row(it) for it in self.list.selectedItems())

    def _update_buttons(self):
        has = bool(self.sprites)
        n = len(self.list.selectedItems())
        self.save_all_btn.setEnabled(has)
        self.send_btn.setEnabled(has)
        self.save_sel_btn.setEnabled(n > 0)
        self.save_sel_btn.setText(f"Save selected ({n})…" if n else "Save selected…")

    def _sync_highlight(self):
        self.view.set_highlight([self.sprites[r].cell for r in self.selected_rows()])
        self._update_buttons()

    def _on_sheet_clicked(self, x: float, y: float, mods):
        hit = None
        for i, s in enumerate(self.sprites):
            c = s.cell
            if c.x <= x < c.x + c.w and c.y <= y < c.y + c.h:
                hit = i
                break
        if hit is None:
            if not mods & (Qt.ControlModifier | Qt.ShiftModifier):
                self.list.clearSelection()
            return
        it = self.list.item(hit)
        if mods & (Qt.ControlModifier | Qt.ShiftModifier):
            it.setSelected(not it.isSelected())
        else:
            self.list.clearSelection()
            it.setSelected(True)
        self.list.setCurrentItem(it, QItemSelectionModel.NoUpdate)
        self.list.scrollToItem(it)

    # ---------------------------------------------------------------- actions
    def preview(self, i: int):
        if 0 <= i < len(self.sprites):
            PreviewDialog(self, self.sprites[i].image, self.name_for(i), lambda: self.save_one(i)).exec()

    def _context_menu(self, pos):
        it = self.list.itemAt(pos)
        if it is None:
            return
        i = self.list.row(it)
        if not it.isSelected():
            self.list.clearSelection()
            it.setSelected(True)
        menu = QMenu(self)
        menu.addAction("Preview", lambda: self.preview(i))
        menu.addAction("Save this sprite…", lambda: self.save_one(i))
        n = len(self.list.selectedItems())
        if n > 1:
            menu.addAction(f"Save {n} selected…", self.save_selected)
        menu.addAction("Copy image", lambda: QGuiApplication.clipboard().setImage(pil_to_qimage(self.sprites[i].image)))
        menu.exec(self.list.viewport().mapToGlobal(pos))

    def save_one(self, i: int):
        if not 0 <= i < len(self.sprites):
            return
        default = str(Path(last_dir()) / f"{self.name_for(i)}.png")
        path, _ = QFileDialog.getSaveFileName(self, "Save sprite", default, "PNG image (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        self.sprites[i].image.save(path)
        remember_dir(path)
        self.status.emit(f"Saved {path}")

    def save_selected(self):
        rows = self.selected_rows()
        if rows:
            self.save_many(rows)

    def save_many(self, rows: list[int]):
        if not rows:
            return
        if len(rows) == 1:
            self.save_one(rows[0])
            return
        folder = QFileDialog.getExistingDirectory(self, f"Choose a folder for {len(rows)} sprites", last_dir())
        if not folder:
            return
        targets = [(i, Path(folder) / f"{self.name_for(i)}.png") for i in rows]
        clashes = [p for _, p in targets if p.exists()]
        if clashes:
            ans = QMessageBox.question(
                self, APP_NAME,
                f"{len(clashes)} of these files already exist in that folder.\nOverwrite them?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.No)
            if ans == QMessageBox.Cancel:
                return
            if ans == QMessageBox.No:
                targets = [(i, p) for i, p in targets if not p.exists()]
        for i, p in targets:
            self.sprites[i].image.save(p)
        settings().setValue("lastDir", folder)
        self.status.emit(f"Saved {len(targets)} sprites to {folder}")

    def _send_to_pack(self):
        rows = self.selected_rows() or list(range(len(self.sprites)))
        self.sendToPack.emit([(self.name_for(i), self.sprites[i].image.copy()) for i in rows])


# ====================================================================== pack tab

class SpriteOrderList(QListWidget):
    """Reorderable sprite list that also accepts image files dropped from outside."""

    filesDropped = Signal(list)
    reordered = Signal()

    def __init__(self):
        super().__init__()
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setAcceptDrops(True)
        self.setIconSize(QSize(44, 44))
        self.setSpacing(2)

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
            paths = image_paths(e.mimeData().urls())
            e.acceptProposedAction()
            if paths:
                self.filesDropped.emit(paths)
            return
        super().dropEvent(e)
        QTimer.singleShot(0, self.reordered.emit)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.count() == 0:
            p = QPainter(self.viewport())
            vr = self.viewport().rect().adjusted(16, 16, -16, -16)
            p.setPen(QPen(QColor(110, 110, 118), 2, Qt.DashLine))
            p.drawRoundedRect(vr, 12, 12)
            p.setPen(QColor(160, 160, 168))
            p.drawText(vr, Qt.AlignCenter | Qt.TextWordWrap,
                       "Drop sprite images (or a folder) here\nor click “Add sprites…”")
            p.end()

    def mouseDoubleClickEvent(self, e):
        if self.count() == 0:
            self.filesDropped.emit([])  # empty list = open the file picker
            return
        super().mouseDoubleClickEvent(e)


class PackTab(QWidget):
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self.entries: dict[int, dict] = {}
        self._next_id = 0
        self.result: core.PackResult | None = None
        self.bg_color = QColor(0, 0, 0, 0)

        self._timer = QTimer(self, singleShot=True, interval=120)
        self._timer.timeout.connect(self.repack)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([480, 820])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(splitter)
        self._update_buttons()

    # ---------------------------------------------------------------- layout
    def _build_left(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)

        top = QHBoxLayout()
        title = QLabel("Sprites (in order)")
        title.setObjectName("paneTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("hint")
        add_btn = QPushButton("Add sprites…")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self.add_dialog)
        top.addWidget(title)
        top.addWidget(self.count_label)
        top.addStretch()
        top.addWidget(add_btn)
        lay.addLayout(top)

        self.list = SpriteOrderList()
        self.list.filesDropped.connect(lambda p: self.add_files(p) if p else self.add_dialog())
        self.list.reordered.connect(self._after_reorder)
        self.list.itemSelectionChanged.connect(self._update_buttons)
        self.list.itemDoubleClicked.connect(self._preview_item)
        lay.addWidget(self.list, 1)

        row1 = QHBoxLayout()
        self.up_btn = QPushButton("▲ Up")
        self.up_btn.clicked.connect(lambda: self.move_selected(-1))
        self.down_btn = QPushButton("▼ Down")
        self.down_btn.clicked.connect(lambda: self.move_selected(1))
        self.top_btn = QPushButton("To top")
        self.top_btn.clicked.connect(lambda: self.move_selected(-10**9))
        self.bottom_btn = QPushButton("To bottom")
        self.bottom_btn.clicked.connect(lambda: self.move_selected(10**9))
        for b in (self.up_btn, self.down_btn, self.top_btn, self.bottom_btn):
            row1.addWidget(b)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        self.sort_btn = QPushButton("Sort A→Z")
        self.sort_btn.clicked.connect(self.sort_by_name)
        self.rev_btn = QPushButton("Reverse")
        self.rev_btn.clicked.connect(self.reverse)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn = QPushButton("Clear all")
        self.clear_btn.clicked.connect(self.clear)
        for b in (self.sort_btn, self.rev_btn, self.remove_btn, self.clear_btn):
            row2.addWidget(b)
        lay.addLayout(row2)
        lay.addWidget(hint("Drag sprites in the list to reorder them. Double-click one to preview it. Del removes the selection."))

        del_act = QAction(self.list)
        del_act.setShortcut(QKeySequence.Delete)
        del_act.setShortcutContext(Qt.WidgetShortcut)
        del_act.triggered.connect(self.remove_selected)
        self.list.addAction(del_act)
        return w

    def _build_right(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 0, 0, 0)

        top = QHBoxLayout()
        title = QLabel("Packed sheet")
        title.setObjectName("paneTitle")
        self.view = ImageView("The packed sprite sheet shows up here", accept_drops=True)
        self.view.filesDropped.connect(self.add_files)
        self.view.emptyClicked.connect(self.add_dialog)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(ZoomBar(self.view))
        lay.addLayout(top)

        self.info = QLabel("")
        self.info.setObjectName("hint")
        lay.addWidget(self.info)
        lay.addWidget(self.view, 1)

        box = QGroupBox("Layout")
        g = QGridLayout(box)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(6)
        self.sp_cols = spin(0, 1000, 0, special="Auto", suffix="")
        self.sp_rows = spin(0, 1000, 0, special="Auto", suffix="")
        self.sp_cw = spin(0, 16384, 0, special="Auto (largest)")
        self.sp_ch = spin(0, 16384, 0, special="Auto (largest)")
        self.sp_pad = spin(0, 4096, 0)
        self.sp_margin = spin(0, 4096, 0)
        self.cb_align = QComboBox()
        for label, key in (("Center", "center"), ("Bottom center", "bottom"), ("Top-left", "topleft")):
            self.cb_align.addItem(label, key)
        self.cb_order = QComboBox()
        self.cb_order.addItem("Row by row (→ then ↓)", "row")
        self.cb_order.addItem("Column by column (↓ then →)", "col")
        self.cb_bg = QComboBox()
        self.cb_bg.addItems(["Transparent", "Solid color"])
        self.bg_btn = QPushButton()
        self.bg_btn.setFixedWidth(44)
        self.bg_btn.setToolTip("Pick the background color")
        self.bg_btn.clicked.connect(self._pick_bg)
        self.ck_grid = QCheckBox("Show cell grid")
        self.ck_grid.setChecked(True)
        self.ck_grid.toggled.connect(self._update_grid)

        g.addWidget(QLabel("Columns"), 0, 0)
        g.addWidget(self.sp_cols, 0, 1)
        g.addWidget(QLabel("Rows"), 0, 2)
        g.addWidget(self.sp_rows, 0, 3)
        g.addWidget(QLabel("Cell width"), 1, 0)
        g.addWidget(self.sp_cw, 1, 1)
        g.addWidget(QLabel("Cell height"), 1, 2)
        g.addWidget(self.sp_ch, 1, 3)
        g.addWidget(QLabel("Gap"), 2, 0)
        g.addWidget(self.sp_pad, 2, 1)
        g.addWidget(QLabel("Margin"), 2, 2)
        g.addWidget(self.sp_margin, 2, 3)
        g.addWidget(QLabel("Align in cell"), 3, 0)
        g.addWidget(self.cb_align, 3, 1)
        g.addWidget(QLabel("Fill order"), 3, 2)
        g.addWidget(self.cb_order, 3, 3)
        bg_row = QHBoxLayout()
        bg_row.addWidget(self.cb_bg, 1)
        bg_row.addWidget(self.bg_btn)
        g.addWidget(QLabel("Background"), 4, 0)
        g.addLayout(bg_row, 4, 1)
        g.addWidget(self.ck_grid, 4, 2, 1, 2)
        for col in (1, 3):
            g.setColumnStretch(col, 1)
        lay.addWidget(box)

        for sb in (self.sp_cols, self.sp_rows, self.sp_cw, self.sp_ch, self.sp_pad, self.sp_margin):
            sb.valueChanged.connect(self._schedule)
        for cb in (self.cb_align, self.cb_order, self.cb_bg):
            cb.currentIndexChanged.connect(self._schedule)
        self.cb_bg.currentIndexChanged.connect(self._update_bg_button)
        self._update_bg_button()

        bottom = QHBoxLayout()
        bottom.addStretch()
        self.export_btn = QPushButton("Export PNG…")
        self.export_btn.clicked.connect(lambda: self.export(with_json=False))
        self.export_json_btn = QPushButton("Export PNG + JSON…")
        self.export_json_btn.setObjectName("primary")
        self.export_json_btn.setToolTip("Also writes a .json file with each frame's name and position.")
        self.export_json_btn.clicked.connect(lambda: self.export(with_json=True))
        bottom.addWidget(self.export_btn)
        bottom.addWidget(self.export_json_btn)
        lay.addLayout(bottom)
        return w

    # ---------------------------------------------------------------- entries
    def add_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add sprites", last_dir(), IMAGE_FILTER)
        if paths:
            self.add_files(paths)

    def add_files(self, paths: list[str]):
        added, failed = [], []
        for p in paths:
            try:
                added.append((Path(p).stem, core.load_rgba(p)))
            except Exception:  # noqa: BLE001
                failed.append(Path(p).name)
        if paths:
            remember_dir(paths[0])
        self.add_images(added)
        if failed:
            QMessageBox.warning(self, APP_NAME, "Could not open:\n" + "\n".join(failed[:20]))

    def add_images(self, items: list[tuple[str, Image.Image]]):
        for name, img in items:
            eid = self._next_id
            self._next_id += 1
            pm = pil_to_pixmap(img)
            self.entries[eid] = {"name": name, "image": img, "pixmap": pm}
            it = QListWidgetItem(make_icon(thumb_pixmap(pm, 44)), "")
            it.setData(ROLE_ID, eid)
            it.setToolTip(f"{name}\n{img.width} × {img.height} px")
            self.list.addItem(it)
        if items:
            self.status.emit(f"Added {len(items)} sprite(s)")
        self._after_reorder()

    def _entry(self, row: int) -> dict:
        return self.entries[self.list.item(row).data(ROLE_ID)]

    def ordered(self) -> list[dict]:
        return [self._entry(r) for r in range(self.list.count())]

    def _renumber(self):
        n = self.list.count()
        digits = len(str(n))
        for r in range(n):
            e = self._entry(r)
            img = e["image"]
            self.list.item(r).setText(f"{r + 1:>{digits}}.  {e['name']}    {img.width}×{img.height}")
        self.count_label.setText(f"{n} sprites" if n else "")

    def _after_reorder(self):
        self._renumber()
        self._update_buttons()
        self._schedule()

    def selected_rows(self) -> list[int]:
        return sorted(self.list.row(it) for it in self.list.selectedItems())

    def move_selected(self, delta: int):
        rows = self.selected_rows()
        if not rows:
            return
        n = self.list.count()
        ids = [self.list.item(r).data(ROLE_ID) for r in range(n)]
        picked = [ids[r] for r in rows]
        rest = [i for r, i in enumerate(ids) if r not in rows]
        # Insert the selected block at its new position, keeping its internal order.
        new_start = max(0, min(rows[0] + delta, n - len(rows)))
        new_ids = rest[:new_start] + picked + rest[new_start:]
        self._rebuild(new_ids, picked)

    def _rebuild(self, ids: list[int], select: list[int] = ()):
        self.list.blockSignals(True)
        items = {self.list.item(r).data(ROLE_ID): self.list.item(r) for r in range(self.list.count())}
        while self.list.count():
            self.list.takeItem(0)
        for i in ids:
            self.list.addItem(items[i])
        for i in select:
            items[i].setSelected(True)
        if select:
            self.list.scrollToItem(items[select[0]])
        self.list.blockSignals(False)
        self._after_reorder()

    def sort_by_name(self):
        ids = [self.list.item(r).data(ROLE_ID) for r in range(self.list.count())]
        ids.sort(key=lambda i: _natural_key(self.entries[i]["name"]))
        self._rebuild(ids)

    def reverse(self):
        ids = [self.list.item(r).data(ROLE_ID) for r in range(self.list.count())]
        self._rebuild(ids[::-1])

    def remove_selected(self):
        for r in reversed(self.selected_rows()):
            it = self.list.takeItem(r)
            self.entries.pop(it.data(ROLE_ID), None)
        self._after_reorder()

    def clear(self):
        if self.list.count() and QMessageBox.question(self, APP_NAME, "Remove all sprites?") != QMessageBox.Yes:
            return
        self.list.clear()
        self.entries.clear()
        self._after_reorder()

    def _preview_item(self, it):
        e = self.entries[it.data(ROLE_ID)]
        PreviewDialog(self, e["image"], e["name"], lambda: self._save_single(e)).exec()

    def _save_single(self, e: dict):
        default = str(Path(last_dir()) / f"{e['name']}.png")
        path, _ = QFileDialog.getSaveFileName(self, "Save sprite", default, "PNG image (*.png)")
        if path:
            e["image"].save(path if path.lower().endswith(".png") else path + ".png")
            remember_dir(path)

    def _update_buttons(self):
        n = self.list.count()
        sel = bool(self.list.selectedItems())
        for b in (self.up_btn, self.down_btn, self.top_btn, self.bottom_btn, self.remove_btn):
            b.setEnabled(sel)
        for b in (self.sort_btn, self.rev_btn, self.clear_btn):
            b.setEnabled(n > 1 if b is not self.clear_btn else n > 0)
        has = self.result is not None
        self.export_btn.setEnabled(has)
        self.export_json_btn.setEnabled(has)

    # ---------------------------------------------------------------- packing
    def _pick_bg(self):
        c = QColorDialog.getColor(self.bg_color if self.bg_color.alpha() else QColor(255, 0, 255),
                                  self, "Background color", QColorDialog.ShowAlphaChannel)
        if c.isValid():
            self.bg_color = c
            self.cb_bg.setCurrentIndex(1)
            self._update_bg_button()
            self._schedule()

    def _update_bg_button(self):
        solid = self.cb_bg.currentIndex() == 1
        if solid and self.bg_color.alpha() == 0:
            self.bg_color = QColor(255, 0, 255)
        c = self.bg_color if solid else QColor(70, 70, 76)
        self.bg_btn.setStyleSheet(f"background:{c.name()}; border:1px solid #666; border-radius:4px;")

    def pack_settings(self) -> core.PackSettings:
        bg = (0, 0, 0, 0)
        if self.cb_bg.currentIndex() == 1:
            c = self.bg_color
            bg = (c.red(), c.green(), c.blue(), c.alpha())
        return core.PackSettings(
            cols=self.sp_cols.value(), rows=self.sp_rows.value(),
            cell_w=self.sp_cw.value(), cell_h=self.sp_ch.value(),
            padding=self.sp_pad.value(), margin=self.sp_margin.value(),
            align=self.cb_align.currentData(), order=self.cb_order.currentData(),
            background=bg,
        )

    def _schedule(self):
        self._timer.start()

    def repack(self):
        entries = self.ordered()
        if not entries:
            self.result = None
            self.view.clear_image()
            self.info.setText("")
            self._update_buttons()
            return
        s = self.pack_settings()
        try:
            res = core.pack_sprites([e["image"] for e in entries], [e["name"] for e in entries], s)
        except ValueError as exc:
            self.result = None
            self.info.setText(f"<span style='color:#ff7a7a'>{exc}</span>")
            self._update_buttons()
            return
        first = self.result is None
        self.result = res
        self.view.set_pixmap(pil_to_pixmap(res.image), fit=first or self.view._auto_fit)
        self._update_grid()
        empty = res.cols * res.rows - len(entries)
        extra = f" · {empty} empty cell{'s' if empty != 1 else ''}" if empty else ""
        self.info.setText(f"{res.image.width} × {res.image.height} px  ·  {res.cols} columns × {res.rows} rows"
                          f"  ·  cell {res.cell_w} × {res.cell_h} px{extra}")
        self._update_buttons()

    def _update_grid(self):
        if self.result is not None:
            self.view.set_grid(self.result.cells if self.ck_grid.isChecked() else [])

    def export(self, with_json: bool):
        if self.result is None:
            return
        default = str(Path(last_dir()) / "spritesheet.png")
        path, _ = QFileDialog.getSaveFileName(self, "Export sprite sheet", default, "PNG image (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        self.result.image.save(path)
        remember_dir(path)
        msg = f"Saved {path}"
        if with_json:
            jpath = str(Path(path).with_suffix(".json"))
            meta = core.pack_metadata(self.result, Path(path).name, self.pack_settings())
            Path(jpath).write_text(json.dumps(meta, indent=2), encoding="utf-8")
            msg += f" and {Path(jpath).name}"
        self.status.emit(msg)


def _natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


# ====================================================================== window

STYLE = """
QWidget { font-size: 10pt; }
QLabel#paneTitle { font-size: 13pt; font-weight: 600; color: #f2f2f2; }
QLabel#hint { color: #9a9aa3; }
QGroupBox { border: 1px solid #3a3a40; border-radius: 8px; margin-top: 14px; padding: 10px 8px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #ffb02e; font-weight: 600; }
QFrame#sep { color: #3a3a40; }
QPushButton { padding: 5px 12px; border-radius: 6px; background: #3a3a40; border: 1px solid #4a4a52; }
QPushButton:hover { background: #46464e; }
QPushButton:pressed { background: #2f2f35; }
QPushButton:disabled { color: #6c6c74; background: #303035; border-color: #38383e; }
QPushButton#primary { background: #ffb02e; color: #1e1e21; border: 1px solid #ffb02e; font-weight: 600; }
QPushButton#primary:hover { background: #ffc254; }
QPushButton#primary:disabled { background: #5a4a2c; color: #8a7a5c; border-color: #5a4a2c; }
QListWidget { background: #232327; border: 1px solid #3a3a40; border-radius: 8px; padding: 4px; }
QListWidget::item { border-radius: 6px; padding: 2px; }
QListWidget::item:hover { background: #303036; }
QListWidget::item:selected { background: #2b4a6e; color: white; }
QTabWidget::pane { border: none; }
QTabBar::tab { padding: 8px 22px; margin-right: 2px; background: #2a2a2f; border-top-left-radius: 8px;
               border-top-right-radius: 8px; color: #b8b8c0; font-weight: 600; }
QTabBar::tab:selected { background: #3a3a40; color: #ffb02e; }
QSplitter::handle { background: #2a2a2f; width: 4px; }
QComboBox, QLineEdit { padding: 3px 6px; border-radius: 5px; background: #2a2a2f; border: 1px solid #44444b; }
QSpinBox { padding: 2px 4px; }
QStatusBar { color: #9a9aa3; }
"""


def dark_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor(37, 37, 41))
    p.setColor(QPalette.WindowText, QColor(225, 225, 230))
    p.setColor(QPalette.Base, QColor(35, 35, 39))
    p.setColor(QPalette.AlternateBase, QColor(45, 45, 50))
    p.setColor(QPalette.ToolTipBase, QColor(50, 50, 56))
    p.setColor(QPalette.ToolTipText, QColor(230, 230, 235))
    p.setColor(QPalette.Text, QColor(225, 225, 230))
    p.setColor(QPalette.Button, QColor(58, 58, 64))
    p.setColor(QPalette.ButtonText, QColor(225, 225, 230))
    p.setColor(QPalette.Highlight, QColor(43, 74, 110))
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.Link, ACCENT)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(110, 110, 118))
    return p


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.unpack = UnpackTab()
        self.pack = PackTab()
        self.tabs.addTab(self.unpack, "Unpack  (slice a sheet)")
        self.tabs.addTab(self.pack, "Pack  (build a sheet)")
        self.setCentralWidget(self.tabs)
        for tab in (self.unpack, self.pack):
            tab.status.connect(lambda m: self.statusBar().showMessage(m, 6000))
        self.unpack.sendToPack.connect(self._send_to_pack)
        self.statusBar().showMessage("Drop a sprite sheet on the left to start slicing.")

        open_act = QAction(self)
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(lambda: (self.unpack.open_dialog() if self.tabs.currentIndex() == 0
                                            else self.pack.add_dialog()))
        self.addAction(open_act)

        geo = settings().value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1360, 860)
        self.tabs.setCurrentIndex(int(settings().value("tab", 0)))

    def _send_to_pack(self, items):
        self.pack.add_images(items)
        self.tabs.setCurrentWidget(self.pack)

    def closeEvent(self, e):
        settings().setValue("geometry", self.saveGeometry())
        settings().setValue("tab", self.tabs.currentIndex())
        super().closeEvent(e)


def resource_path(rel: str) -> Path:
    """Locate bundled files both from source and inside the PyInstaller exe."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / rel


def main():
    if sys.platform == "win32":
        # Own taskbar identity, so Windows shows our icon instead of Python's.
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Yuzu.SpriteTool")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    icon = resource_path("assets/icon.ico")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win.show()
    args = [a for a in sys.argv[1:] if Path(a).suffix.lower() in IMAGE_EXTS]
    if args:
        win.unpack.load_sheet(args[0])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
