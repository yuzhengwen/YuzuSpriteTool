"""Unpack tab: load and slice a sprite sheet (left), then browse/save the sprites (right)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem,
    QMenu, QPushButton, QSlider, QSplitter, QVBoxLayout, QWidget,
)

from ...core import DEFAULT_PREFIX, Sprite, numbered_name
from .. import file_dialogs
from ..dialogs import PreviewDialog
from ..panels import SheetSlicerPanel
from ..qt_image import copy_to_clipboard, pil_to_pixmap, sprite_icon, thumb_pixmap
from ..widgets import SpriteDelegate, hint_label, pane_title, primary_button

THUMB_DELAY_MS = 80
THUMB_MIN, THUMB_MAX, THUMB_DEFAULT = 32, 256, 96
TILE_PAD_W, TILE_PAD_H = 26, 46   # room around a thumbnail for its label
MULTI_SELECT = Qt.ControlModifier | Qt.ShiftModifier


class UnpackTab(QWidget):
    status = Signal(str)
    sendToPack = Signal(list)   # [(name, PIL image)]

    def __init__(self):
        super().__init__()
        self._pixmaps: list[QPixmap] = []
        self._thumb_timer = QTimer(self, singleShot=True, interval=THUMB_DELAY_MS)
        self._thumb_timer.timeout.connect(self._refresh_thumbnails)

        self.slicer = SheetSlicerPanel()
        self.slicer.layout().setContentsMargins(0, 0, 6, 0)
        self.slicer.sliced.connect(self._on_sliced)
        self.slicer.sheetLoaded.connect(self._on_sheet_loaded)
        self.slicer.spriteClicked.connect(self._on_sheet_clicked)
        self.slicer.status.connect(self.status)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.slicer)
        splitter.addWidget(self._build_sprites_pane())
        splitter.setSizes([700, 600])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(splitter)
        self._update_buttons()

    @property
    def sprites(self) -> list[Sprite]:
        return self.slicer.sprites

    def open_dialog(self) -> None:
        self.slicer.open_dialog()

    def load_sheet(self, path: str) -> None:
        self.slicer.load_sheet(path)

    # ================================================================ layout
    def _build_sprites_pane(self) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(6, 0, 0, 0)

        self.count_label = hint_label(wrap=False)
        select_all = QPushButton("Select all")
        select_none = QPushButton("Select none")
        header = QHBoxLayout()
        header.addWidget(pane_title("Sliced sprites"))
        header.addWidget(self.count_label)
        header.addStretch()
        header.addWidget(select_all)
        header.addWidget(select_none)

        self.list = self._make_sprite_grid()
        select_all.clicked.connect(self.list.selectAll)
        select_none.clicked.connect(self.list.clearSelection)

        self.thumb_slider = QSlider(Qt.Horizontal)
        self.thumb_slider.setRange(THUMB_MIN, THUMB_MAX)
        self.thumb_slider.setValue(THUMB_DEFAULT)
        self.thumb_slider.setFixedWidth(140)
        self.thumb_slider.valueChanged.connect(self._thumb_timer.start)
        size_row = QHBoxLayout()
        size_row.addWidget(hint_label("Double-click to preview · hover for the save button · "
                                      "Ctrl/Shift-click to pick several"), 1)
        size_row.addWidget(QLabel("Thumb size"))
        size_row.addWidget(self.thumb_slider)

        lay.addLayout(header)
        lay.addWidget(self.list, 1)
        lay.addLayout(size_row)
        lay.addLayout(self._build_save_row())

        save_shortcut = QAction(self)
        save_shortcut.setShortcut(QKeySequence.Save)
        save_shortcut.triggered.connect(self.save_selected)
        self.addAction(save_shortcut)
        return pane

    def _make_sprite_grid(self) -> QListWidget:
        grid = QListWidget()
        grid.setViewMode(QListView.IconMode)
        grid.setResizeMode(QListView.Adjust)
        grid.setMovement(QListView.Static)
        grid.setSelectionMode(QAbstractItemView.ExtendedSelection)
        grid.setUniformItemSizes(True)
        grid.setSpacing(4)
        grid.setMouseTracking(True)   # needed for the hover save button
        grid.setContextMenuPolicy(Qt.CustomContextMenu)
        grid.customContextMenuRequested.connect(self._show_context_menu)
        grid.itemDoubleClicked.connect(lambda it: self.preview(grid.row(it)))
        grid.itemSelectionChanged.connect(self._on_selection_changed)
        delegate = SpriteDelegate(grid)
        delegate.saveClicked.connect(self.save_one)
        grid.setItemDelegate(delegate)
        return grid

    def _build_save_row(self) -> QHBoxLayout:
        self.prefix = QLineEdit(DEFAULT_PREFIX)
        self.prefix.setMaximumWidth(180)
        self.prefix.textChanged.connect(self._refresh_labels)

        self.send_btn = QPushButton("Send to Pack tab")
        self.send_btn.setToolTip("Copy the selected sprites (or all, if none are selected) into the Pack tab.")
        self.send_btn.clicked.connect(self._send_to_pack)
        self.save_sel_btn = QPushButton("Save selected…")
        self.save_sel_btn.clicked.connect(self.save_selected)
        self.save_all_btn = primary_button("Save all…")
        self.save_all_btn.clicked.connect(lambda: self.save_many(range(len(self.sprites))))

        row = QHBoxLayout()
        row.addWidget(QLabel("File name prefix"))
        row.addWidget(self.prefix)
        row.addStretch()
        for b in (self.send_btn, self.save_sel_btn, self.save_all_btn):
            row.addWidget(b)
        return row

    # ================================================================ reacting to the sheet
    def _on_sheet_loaded(self, path: str) -> None:
        self.prefix.blockSignals(True)
        self.prefix.setText(Path(path).stem)
        self.prefix.blockSignals(False)

    def _on_sliced(self) -> None:
        self._pixmaps = [pil_to_pixmap(s.image) for s in self.sprites]
        self._populate_grid()

    def _on_sheet_clicked(self, index: int, modifiers) -> None:
        """Clicking a cell on the sheet selects its sprite (Ctrl/Shift toggles)."""
        multi = bool(modifiers & MULTI_SELECT)
        if index < 0:
            if not multi:
                self.list.clearSelection()
            return
        item = self.list.item(index)
        if multi:
            item.setSelected(not item.isSelected())
        else:
            self.list.clearSelection()
            item.setSelected(True)
        self.list.setCurrentItem(item, QItemSelectionModel.NoUpdate)
        self.list.scrollToItem(item)

    # ================================================================ sprite grid
    def name_for(self, i: int) -> str:
        return numbered_name(self.prefix.text(), i, len(self.sprites))

    def _label(self, i: int) -> str:
        img = self.sprites[i].image
        return f"{self.name_for(i)}\n{img.width}×{img.height}"

    def _apply_tile_size(self) -> int:
        box = self.thumb_slider.value()
        self.list.setIconSize(QSize(box, box))
        self.list.setGridSize(QSize(box + TILE_PAD_W, box + TILE_PAD_H))
        return box

    def _populate_grid(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        box = self._apply_tile_size()
        for i, (sprite, pm) in enumerate(zip(self.sprites, self._pixmaps)):
            item = QListWidgetItem(sprite_icon(thumb_pixmap(pm, box)), self._label(i))
            item.setToolTip(f"{self.name_for(i)}\n{sprite.image.width} × {sprite.image.height} px\n"
                            f"from x={sprite.cell.x}, y={sprite.cell.y}")
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.count_label.setText(f"{len(self.sprites)} sprites" if self.sprites else "")
        self._update_buttons()

    def _refresh_labels(self) -> None:
        for i in range(self.list.count()):
            self.list.item(i).setText(self._label(i))

    def _refresh_thumbnails(self) -> None:
        box = self._apply_tile_size()
        for i, pm in enumerate(self._pixmaps):
            self.list.item(i).setIcon(sprite_icon(thumb_pixmap(pm, box)))

    def selected_rows(self) -> list[int]:
        return sorted(self.list.row(it) for it in self.list.selectedItems())

    def _on_selection_changed(self) -> None:
        self.slicer.highlight(self.selected_rows())
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_sprites = bool(self.sprites)
        n = len(self.list.selectedItems())
        self.save_all_btn.setEnabled(has_sprites)
        self.send_btn.setEnabled(has_sprites)
        self.save_sel_btn.setEnabled(n > 0)
        self.save_sel_btn.setText(f"Save selected ({n})…" if n else "Save selected…")

    # ================================================================ actions
    def preview(self, i: int) -> None:
        if 0 <= i < len(self.sprites):
            PreviewDialog(self, self.sprites[i].image, self.name_for(i), lambda: self.save_one(i)).exec()

    def _show_context_menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if item is None:
            return
        i = self.list.row(item)
        if not item.isSelected():
            self.list.clearSelection()
            item.setSelected(True)
        menu = QMenu(self)
        menu.addAction("Preview", lambda: self.preview(i))
        menu.addAction("Save this sprite…", lambda: self.save_one(i))
        n = len(self.list.selectedItems())
        if n > 1:
            menu.addAction(f"Save {n} selected…", self.save_selected)
        menu.addAction("Copy image", lambda: copy_to_clipboard(self.sprites[i].image))
        menu.exec(self.list.viewport().mapToGlobal(pos))

    def save_one(self, i: int) -> None:
        if 0 <= i < len(self.sprites):
            path = file_dialogs.save_image_as(self, self.sprites[i].image, self.name_for(i))
            if path:
                self.status.emit(f"Saved {path}")

    def save_selected(self) -> None:
        self.save_many(self.selected_rows())

    def save_many(self, rows) -> None:
        rows = list(rows)
        if not rows:
            return
        if len(rows) == 1:
            self.save_one(rows[0])
            return
        result = file_dialogs.save_images_to_folder(self, [(self.name_for(i), self.sprites[i].image) for i in rows])
        if result:
            count, folder = result
            self.status.emit(f"Saved {count} sprites to {folder}")

    def _send_to_pack(self) -> None:
        rows = self.selected_rows() or range(len(self.sprites))
        self.sendToPack.emit([(self.name_for(i), self.sprites[i].image.copy()) for i in rows])
