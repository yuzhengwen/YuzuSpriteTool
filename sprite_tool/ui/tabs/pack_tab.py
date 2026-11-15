"""Pack tab: collect and order sprites (left) and build the combined sheet (right)."""
from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QListWidgetItem, QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from ... import APP_NAME
from ...core import PackResult, load_rgba, natural_key, pack_metadata, pack_sprites
from .. import file_dialogs, prefs
from ..forms import PackLayoutForm
from ..qt_image import pil_to_pixmap, sprite_icon, thumb_pixmap
from ..theme import error_html
from ..widgets import (
    ImageView, PreviewDialog, SpriteOrderList, ZoomBar, hint_label, pane_title, primary_button,
)
from ..widgets.sprite_order_list import ICON_SIZE

REPACK_DELAY_MS = 120
ROLE_ENTRY_ID = Qt.UserRole + 1
MAX_FAILED_NAMES_SHOWN = 20
TO_END = 10**9   # move distance meaning "all the way"


@dataclass
class PackEntry:
    id: int
    name: str
    image: Image.Image
    pixmap: QPixmap


class PackTab(QWidget):
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self._entries: dict[int, PackEntry] = {}
        self._ids = itertools.count()
        self.result: PackResult | None = None

        self._repack_timer = QTimer(self, singleShot=True, interval=REPACK_DELAY_MS)
        self._repack_timer.timeout.connect(self.repack)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_list_pane())
        splitter.addWidget(self._build_sheet_pane())
        splitter.setSizes([480, 820])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(splitter)
        self._update_buttons()

    # ================================================================ layout
    def _build_list_pane(self) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 0, 6, 0)

        self.count_label = hint_label(wrap=False)
        add_btn = primary_button("Add sprites…")
        add_btn.clicked.connect(self.add_dialog)
        header = QHBoxLayout()
        header.addWidget(pane_title("Sprites (in order)"))
        header.addWidget(self.count_label)
        header.addStretch()
        header.addWidget(add_btn)

        self.list = SpriteOrderList()
        self.list.filesDropped.connect(self.add_files)
        self.list.openRequested.connect(self.add_dialog)
        self.list.reordered.connect(self._on_order_changed)
        self.list.itemSelectionChanged.connect(self._update_buttons)
        self.list.itemDoubleClicked.connect(self._preview_item)

        delete = QAction(self.list)
        delete.setShortcut(QKeySequence.Delete)
        delete.setShortcutContext(Qt.WidgetShortcut)
        delete.triggered.connect(self.remove_selected)
        self.list.addAction(delete)

        self.up_btn = self._button("▲ Up", lambda: self.move_selected(-1))
        self.down_btn = self._button("▼ Down", lambda: self.move_selected(1))
        self.top_btn = self._button("To top", lambda: self.move_selected(-TO_END))
        self.bottom_btn = self._button("To bottom", lambda: self.move_selected(TO_END))
        self.sort_btn = self._button("Sort A→Z", self.sort_by_name)
        self.reverse_btn = self._button("Reverse", self.reverse)
        self.remove_btn = self._button("Remove", self.remove_selected)
        self.clear_btn = self._button("Clear all", self.clear)

        lay.addLayout(header)
        lay.addWidget(self.list, 1)
        lay.addLayout(self._row(self.up_btn, self.down_btn, self.top_btn, self.bottom_btn))
        lay.addLayout(self._row(self.sort_btn, self.reverse_btn, self.remove_btn, self.clear_btn))
        lay.addWidget(hint_label("Drag sprites in the list to reorder them. Double-click one to preview it. "
                                 "Del removes the selection."))
        return pane

    def _build_sheet_pane(self) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(6, 0, 0, 0)

        self.view = ImageView("The packed sprite sheet shows up here")
        self.view.filesDropped.connect(self.add_files)
        self.view.emptyClicked.connect(self.add_dialog)
        header = QHBoxLayout()
        header.addWidget(pane_title("Packed sheet"))
        header.addStretch()
        header.addWidget(ZoomBar(self.view))

        self.info = hint_label(wrap=False)
        self.form = PackLayoutForm()
        self.form.changed.connect(self._schedule_repack)
        self.form.gridToggled.connect(self._update_grid_overlay)

        self.export_btn = self._button("Export PNG…", lambda: self.export(with_json=False))
        self.export_json_btn = primary_button("Export PNG + JSON…")
        self.export_json_btn.setToolTip("Also writes a .json file with each frame's name and position.")
        self.export_json_btn.clicked.connect(lambda: self.export(with_json=True))
        export_row = QHBoxLayout()
        export_row.addStretch()
        export_row.addWidget(self.export_btn)
        export_row.addWidget(self.export_json_btn)

        lay.addLayout(header)
        lay.addWidget(self.info)
        lay.addWidget(self.view, 1)
        lay.addWidget(self.form)
        lay.addLayout(export_row)
        return pane

    @staticmethod
    def _button(text: str, on_click) -> QPushButton:
        b = QPushButton(text)
        b.clicked.connect(on_click)
        return b

    @staticmethod
    def _row(*widgets) -> QHBoxLayout:
        row = QHBoxLayout()
        for w in widgets:
            row.addWidget(w)
        return row

    # ================================================================ adding sprites
    def add_dialog(self) -> None:
        paths = file_dialogs.ask_open_images(self, "Add sprites")
        if paths:
            self.add_files(paths)

    def add_files(self, paths: list[str]) -> None:
        loaded, failed = [], []
        for p in paths:
            try:
                loaded.append((Path(p).stem, load_rgba(p)))
            except Exception:  # noqa: BLE001 - report unreadable files, keep the rest
                failed.append(Path(p).name)
        if paths:
            prefs.remember_dir(paths[0])
        self.add_images(loaded)
        if failed:
            QMessageBox.warning(self, APP_NAME, "Could not open:\n" + "\n".join(failed[:MAX_FAILED_NAMES_SHOWN]))

    def add_images(self, items: list[tuple[str, Image.Image]]) -> None:
        for name, img in items:
            pm = pil_to_pixmap(img)
            entry = PackEntry(next(self._ids), name, img, pm)
            self._entries[entry.id] = entry
            item = QListWidgetItem(sprite_icon(thumb_pixmap(pm, ICON_SIZE)), "")
            item.setData(ROLE_ENTRY_ID, entry.id)
            item.setToolTip(f"{name}\n{img.width} × {img.height} px")
            self.list.addItem(item)
        if items:
            self.status.emit(f"Added {len(items)} sprite(s)")
        self._on_order_changed()

    # ================================================================ order
    def _id_at(self, row: int) -> int:
        return self.list.item(row).data(ROLE_ENTRY_ID)

    def ordered_ids(self) -> list[int]:
        return [self._id_at(r) for r in range(self.list.count())]

    def ordered_entries(self) -> list[PackEntry]:
        return [self._entries[i] for i in self.ordered_ids()]

    def selected_rows(self) -> list[int]:
        return sorted(self.list.row(it) for it in self.list.selectedItems())

    def move_selected(self, delta: int) -> None:
        """Move the selection as one block by `delta` rows, keeping its internal order."""
        rows = self.selected_rows()
        if not rows:
            return
        ids = self.ordered_ids()
        picked = [ids[r] for r in rows]
        selected = set(rows)
        rest = [i for r, i in enumerate(ids) if r not in selected]
        start = max(0, min(rows[0] + delta, len(ids) - len(rows)))
        self._set_order(rest[:start] + picked + rest[start:], select=picked)

    def sort_by_name(self) -> None:
        self._set_order(sorted(self.ordered_ids(), key=lambda i: natural_key(self._entries[i].name)))

    def reverse(self) -> None:
        self._set_order(self.ordered_ids()[::-1])

    def _set_order(self, ids: list[int], select: list[int] = ()) -> None:
        """Rearrange the existing list items into `ids` order."""
        self.list.blockSignals(True)
        items = {self._id_at(r): self.list.item(r) for r in range(self.list.count())}
        while self.list.count():
            self.list.takeItem(0)
        for i in ids:
            self.list.addItem(items[i])
        for i in select:
            items[i].setSelected(True)
        if select:
            self.list.scrollToItem(items[select[0]])
        self.list.blockSignals(False)
        self._on_order_changed()

    def remove_selected(self) -> None:
        for r in reversed(self.selected_rows()):
            self._entries.pop(self.list.takeItem(r).data(ROLE_ENTRY_ID), None)
        self._on_order_changed()

    def clear(self) -> None:
        if self.list.count() and QMessageBox.question(self, APP_NAME, "Remove all sprites?") != QMessageBox.Yes:
            return
        self.list.clear()
        self._entries.clear()
        self._on_order_changed()

    def _on_order_changed(self) -> None:
        self._renumber()
        self._update_buttons()
        self._schedule_repack()

    def _renumber(self) -> None:
        n = self.list.count()
        width = len(str(n))
        for r, e in enumerate(self.ordered_entries()):
            self.list.item(r).setText(f"{r + 1:>{width}}.  {e.name}    {e.image.width}×{e.image.height}")
        self.count_label.setText(f"{n} sprites" if n else "")

    def _update_buttons(self) -> None:
        n = self.list.count()
        has_selection = bool(self.list.selectedItems())
        for b in (self.up_btn, self.down_btn, self.top_btn, self.bottom_btn, self.remove_btn):
            b.setEnabled(has_selection)
        self.sort_btn.setEnabled(n > 1)
        self.reverse_btn.setEnabled(n > 1)
        self.clear_btn.setEnabled(n > 0)
        can_export = self.result is not None
        self.export_btn.setEnabled(can_export)
        self.export_json_btn.setEnabled(can_export)

    def _preview_item(self, item: QListWidgetItem) -> None:
        e = self._entries[item.data(ROLE_ENTRY_ID)]
        PreviewDialog(self, e.image, e.name, lambda: file_dialogs.save_image_as(self, e.image, e.name)).exec()

    # ================================================================ packing
    def _schedule_repack(self) -> None:
        self._repack_timer.start()

    def repack(self) -> None:
        entries = self.ordered_entries()
        if not entries:
            self._show_result(None, "")
            self.view.clear_image()
            return
        try:
            result = pack_sprites([e.image for e in entries], [e.name for e in entries], self.form.settings())
        except ValueError as exc:
            self._show_result(None, error_html(str(exc)))
            return
        keep_view = self.result is not None and not self.view.auto_fit
        self.view.set_pixmap(pil_to_pixmap(result.image), fit=not keep_view)
        self._show_result(result, self._describe(result))
        self._update_grid_overlay()

    @staticmethod
    def _describe(r: PackResult) -> str:
        text = (f"{r.image.width} × {r.image.height} px  ·  {r.cols} columns × {r.rows} rows"
                f"  ·  cell {r.cell_w} × {r.cell_h} px")
        if r.empty_cells:
            text += f" · {r.empty_cells} empty cell{'s' if r.empty_cells != 1 else ''}"
        return text

    def _show_result(self, result: PackResult | None, info: str) -> None:
        self.result = result
        self.info.setText(info)
        self._update_buttons()

    def _update_grid_overlay(self) -> None:
        if self.result is not None:
            self.view.set_grid(self.result.cells if self.form.show_grid.isChecked() else [])

    def export(self, with_json: bool) -> None:
        if self.result is None:
            return
        path = file_dialogs.ask_save_png(self, "Export sprite sheet", "spritesheet")
        if not path:
            return
        self.result.image.save(path)
        message = f"Saved {path}"
        if with_json:
            json_path = Path(path).with_suffix(".json")
            meta = pack_metadata(self.result, Path(path).name, self.form.settings())
            json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            message += f" and {json_path.name}"
        self.status.emit(message)
