"""Ordered list of individual sprites: add, reorder, remove, and crop/resize each one.

Used by the Pack tab and the Animate tab's "Sprites" mode.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ... import APP_NAME
from ...core import SpriteEdit, apply_edit, load_rgba, natural_key
from .. import file_dialogs, prefs
from ..dialogs import SpriteEditorDialog
from ..qt_image import pil_to_pixmap, sprite_icon, thumb_pixmap
from ..widgets import PackEntryDelegate, SpriteOrderList, hint_label, pane_title, primary_button
from ..widgets.pack_entry_delegate import ROLE_EDITED, ROLE_ENTRY_ID
from ..widgets.sprite_order_list import ICON_SIZE

MAX_FAILED_NAMES_SHOWN = 20
TO_END = 10**9   # move distance meaning "all the way"
HINT = ("Drag to reorder. Click a thumbnail or Edit to crop/resize a sprite; "
        "✕ reverts it to the original. Del removes the selection.")


@dataclass
class SpriteEntry:
    """One sprite in the list. `original` is never modified; `image` is original + edit."""

    id: int
    name: str
    original: Image.Image
    edit: SpriteEdit | None = None
    image: Image.Image | None = None
    pixmap: QPixmap | None = None

    def __post_init__(self):
        self.set_edit(self.edit)

    @property
    def is_edited(self) -> bool:
        return self.edit is not None

    def set_edit(self, edit: SpriteEdit | None) -> None:
        self.edit = edit
        self.image = apply_edit(self.original, edit)
        self.pixmap = pil_to_pixmap(self.image)


class SpriteListPanel(QWidget):
    changed = Signal()      # sprites added/removed/reordered/edited
    status = Signal(str)

    def __init__(self, title: str = "Sprites (in order)"):
        super().__init__()
        self._entries: dict[int, SpriteEntry] = {}
        self._ids = itertools.count()
        self._build(title)
        self._refresh()

    # ================================================================ layout
    def _build(self, title: str) -> None:
        self.count_label = hint_label(wrap=False)
        add_btn = primary_button("Add sprites…")
        add_btn.clicked.connect(self.add_dialog)
        header = QHBoxLayout()
        header.addWidget(pane_title(title))
        header.addWidget(self.count_label)
        header.addStretch()
        header.addWidget(add_btn)

        self.list = SpriteOrderList()
        self.list.filesDropped.connect(self.add_files)
        self.list.openRequested.connect(self.add_dialog)
        self.list.reordered.connect(self._refresh_and_notify)
        self.list.itemSelectionChanged.connect(self._update_buttons)
        self.list.itemDoubleClicked.connect(lambda item: self.open_editor(self.list.row(item)))
        self.list.setMouseTracking(True)   # hover feedback on the row buttons
        delegate = PackEntryDelegate(self.list)
        delegate.editRequested.connect(self.open_editor)
        delegate.revertRequested.connect(self.revert)
        self.list.setItemDelegate(delegate)

        delete = QAction(self.list)
        delete.setShortcut(QKeySequence.Delete)
        delete.setShortcutContext(Qt.WidgetShortcut)
        delete.triggered.connect(self.remove_selected)
        self.list.addAction(delete)

        self.up_btn = _button("▲ Up", lambda: self.move_selected(-1))
        self.down_btn = _button("▼ Down", lambda: self.move_selected(1))
        self.top_btn = _button("To top", lambda: self.move_selected(-TO_END))
        self.bottom_btn = _button("To bottom", lambda: self.move_selected(TO_END))
        self.sort_btn = _button("Sort A→Z", self.sort_by_name)
        self.reverse_btn = _button("Reverse", self.reverse)
        self.remove_btn = _button("Remove", self.remove_selected)
        self.clear_btn = _button("Clear all", self.clear)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(header)
        lay.addWidget(self.list, 1)
        lay.addLayout(_row(self.up_btn, self.down_btn, self.top_btn, self.bottom_btn))
        lay.addLayout(_row(self.sort_btn, self.reverse_btn, self.remove_btn, self.clear_btn))
        lay.addWidget(hint_label(HINT))

    # ================================================================ reading
    def __len__(self) -> int:
        return self.list.count()

    def entries(self) -> list[SpriteEntry]:
        """Sprites in list order."""
        return [self._entries[i] for i in self._ordered_ids()]

    def entry_at(self, row: int) -> SpriteEntry | None:
        item = self.list.item(row)
        return self._entries.get(item.data(ROLE_ENTRY_ID)) if item is not None else None

    def selected_rows(self) -> list[int]:
        return sorted(self.list.row(it) for it in self.list.selectedItems())

    def _ordered_ids(self) -> list[int]:
        return [self.list.item(r).data(ROLE_ENTRY_ID) for r in range(self.list.count())]

    # ================================================================ adding
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
            entry = SpriteEntry(next(self._ids), name, img)
            self._entries[entry.id] = entry
            item = QListWidgetItem()
            item.setData(ROLE_ENTRY_ID, entry.id)
            self._sync_item(item, entry)
            self.list.addItem(item)
        if items:
            self.status.emit(f"Added {len(items)} sprite(s)")
        self._refresh_and_notify()

    # ================================================================ ordering & removing
    def move_selected(self, delta: int) -> None:
        """Move the selection as one block by `delta` rows, keeping its internal order."""
        rows = self.selected_rows()
        if not rows:
            return
        ids = self._ordered_ids()
        picked = [ids[r] for r in rows]
        selected = set(rows)
        rest = [i for r, i in enumerate(ids) if r not in selected]
        start = max(0, min(rows[0] + delta, len(ids) - len(rows)))
        self._set_order(rest[:start] + picked + rest[start:], select=picked)

    def sort_by_name(self) -> None:
        self._set_order(sorted(self._ordered_ids(), key=lambda i: natural_key(self._entries[i].name)))

    def reverse(self) -> None:
        self._set_order(self._ordered_ids()[::-1])

    def _set_order(self, ids: list[int], select: list[int] = ()) -> None:
        """Rearrange the existing list items into `ids` order."""
        self.list.blockSignals(True)
        items = {self.list.item(r).data(ROLE_ENTRY_ID): self.list.item(r) for r in range(self.list.count())}
        while self.list.count():
            self.list.takeItem(0)
        for i in ids:
            self.list.addItem(items[i])
        for i in select:
            items[i].setSelected(True)
        if select:
            self.list.scrollToItem(items[select[0]])
        self.list.blockSignals(False)
        self._refresh_and_notify()

    def remove_selected(self) -> None:
        for r in reversed(self.selected_rows()):
            self._entries.pop(self.list.takeItem(r).data(ROLE_ENTRY_ID), None)
        self._refresh_and_notify()

    def clear(self, confirm: bool = True) -> None:
        if confirm and self.list.count() and \
                QMessageBox.question(self, APP_NAME, "Remove all sprites?") != QMessageBox.Yes:
            return
        self.list.clear()
        self._entries.clear()
        self._refresh_and_notify()

    # ================================================================ editing
    def open_editor(self, row: int) -> None:
        entry = self.entry_at(row)
        if entry is None:
            return
        dialog = SpriteEditorDialog(self, entry.original, entry.name, entry.edit)
        if dialog.exec() == SpriteEditorDialog.Accepted:
            self._apply_edit(row, entry, dialog.edit)

    def revert(self, row: int) -> None:
        entry = self.entry_at(row)
        if entry is not None and entry.is_edited:
            self._apply_edit(row, entry, None)
            self.status.emit(f"Reverted {entry.name} to the original")

    def _apply_edit(self, row: int, entry: SpriteEntry, edit: SpriteEdit | None) -> None:
        entry.set_edit(edit)
        self._sync_item(self.list.item(row), entry)
        self._refresh_and_notify()

    @staticmethod
    def _sync_item(item: QListWidgetItem, entry: SpriteEntry) -> None:
        """Refresh a list item's thumbnail, tooltip and edited flag from its entry."""
        item.setIcon(sprite_icon(thumb_pixmap(entry.pixmap, ICON_SIZE)))
        item.setData(ROLE_EDITED, entry.is_edited)
        size = f"{entry.image.width} × {entry.image.height} px"
        if entry.is_edited:
            size += f" (original {entry.original.width} × {entry.original.height})"
        item.setToolTip(f"{entry.name}\n{size}")

    # ================================================================ refresh
    def _refresh_and_notify(self) -> None:
        self._refresh()
        self.changed.emit()

    def _refresh(self) -> None:
        n = self.list.count()
        width = len(str(n))
        for r, e in enumerate(self.entries()):
            edited = f"  (edited, was {e.original.width}×{e.original.height})" if e.is_edited else ""
            self.list.item(r).setText(f"{r + 1:>{width}}.  {e.name}    {e.image.width}×{e.image.height}{edited}")
        self.count_label.setText(f"{n} sprites" if n else "")
        self._update_buttons()

    def _update_buttons(self) -> None:
        n = self.list.count()
        has_selection = bool(self.list.selectedItems())
        for b in (self.up_btn, self.down_btn, self.top_btn, self.bottom_btn, self.remove_btn):
            b.setEnabled(has_selection)
        self.sort_btn.setEnabled(n > 1)
        self.reverse_btn.setEnabled(n > 1)
        self.clear_btn.setEnabled(n > 0)


def _button(text: str, on_click) -> QPushButton:
    b = QPushButton(text)
    b.clicked.connect(on_click)
    return b


def _row(*widgets) -> QHBoxLayout:
    row = QHBoxLayout()
    for w in widgets:
        row.addWidget(w)
    return row
