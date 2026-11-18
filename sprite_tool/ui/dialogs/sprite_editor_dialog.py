"""Sprite editor popup: enlarged view of the original with crop and resize controls."""
from __future__ import annotations

from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ... import APP_NAME
from ...core import SpriteEdit, alpha_bounds, apply_edit, full_rect, normalize_edit
from .. import file_dialogs
from ..forms import CropForm, ResizeForm
from ..qt_image import pil_to_pixmap
from ..widgets import CropView, ImageView, ZoomBar, hint_label, pane_title, primary_button

PREVIEW_DELAY_MS = 60
CONTROLS_WIDTH = 360
RESULT_VIEW_MIN_H = 180


class SpriteEditorDialog(QDialog):
    """Edit a sprite non-destructively. After exec() returns Accepted, read `.edit`.

    `.edit` is None when the result equals the original (nothing to apply).
    """

    def __init__(self, parent: QWidget, original: Image.Image, name: str, edit: SpriteEdit | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit sprite: {name}")
        self.original = original
        self.name = name
        self.edit: SpriteEdit | None = edit

        self._preview_timer = QTimer(self, singleShot=True, interval=PREVIEW_DELAY_MS)
        self._preview_timer.timeout.connect(self._update_preview)

        self._build()
        self._load(edit)
        self._fit_to_screen()

    # ================================================================ layout
    def _build(self) -> None:
        self.crop_view = CropView()
        self.crop_view.set_pixmap(pil_to_pixmap(self.original))
        self.crop_view.cropDrawn.connect(lambda rect: self.crop_form.set_rect(rect))

        source_header = QHBoxLayout()
        source_header.addWidget(pane_title("Original"))
        source_header.addWidget(hint_label(f"{self.original.width} × {self.original.height} px", wrap=False))
        source_header.addStretch()
        source_header.addWidget(ZoomBar(self.crop_view))
        source = QVBoxLayout()
        source.addLayout(source_header)
        source.addWidget(self.crop_view, 1)
        source.addWidget(hint_label("Drag to draw the crop area · scroll to zoom · right-drag to pan", wrap=False))

        self.crop_form = CropForm()
        self.crop_form.set_image_size(self.original.width, self.original.height)
        self.crop_form.changed.connect(self._on_crop_changed)
        self.crop_form.trimRequested.connect(self._trim)

        self.resize_form = ResizeForm()
        self.resize_form.set_base_size(self.original.width, self.original.height)
        self.resize_form.changed.connect(self._schedule_preview)

        self.result_info = hint_label(wrap=False)
        self.result_view = ImageView(accept_drops=False)
        self.result_view.setMinimumHeight(RESULT_VIEW_MIN_H)

        controls = QVBoxLayout()
        controls.addWidget(self.crop_form)
        controls.addWidget(self.resize_form)
        controls.addWidget(pane_title("Result"))
        controls.addWidget(self.result_info)
        controls.addWidget(self.result_view, 1)
        controls_box = QWidget()
        controls_box.setLayout(controls)
        controls_box.setFixedWidth(CONTROLS_WIDTH)
        controls.setContentsMargins(0, 0, 0, 0)

        body = QHBoxLayout()
        body.addLayout(source, 1)
        body.addWidget(controls_box)

        reset_btn = QPushButton("Reset all")
        reset_btn.setToolTip("Clear the crop and resize (back to the original).")
        reset_btn.clicked.connect(self._reset)
        save_btn = QPushButton("Save result PNG…")
        save_btn.clicked.connect(self._save_result)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        apply_btn = primary_button("Apply")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._accept)
        buttons = QHBoxLayout()
        buttons.addWidget(reset_btn)
        buttons.addWidget(save_btn)
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(apply_btn)

        lay = QVBoxLayout(self)
        lay.addLayout(body, 1)
        lay.addLayout(buttons)

    def _fit_to_screen(self) -> None:
        screen = self.screen().availableGeometry()
        self.resize(int(min(1180, screen.width() * 0.9)), int(min(780, screen.height() * 0.9)))

    # ================================================================ state
    def _load(self, edit: SpriteEdit | None) -> None:
        if edit and edit.crop:
            self.crop_form.set_rect(edit.crop)
        self._on_crop_changed()
        self.resize_form.set_state(edit.size if edit else None, edit.resample if edit else "nearest")
        self._update_preview()

    def current_edit(self) -> SpriteEdit | None:
        draft = SpriteEdit(crop=self.crop_form.active_rect(),
                           size=self.resize_form.target_size(),
                           resample=self.resize_form.resample())
        return normalize_edit(self.original, draft)

    def current_result(self) -> Image.Image:
        return apply_edit(self.original, self.current_edit())

    # ================================================================ reactions
    def _on_crop_changed(self) -> None:
        rect = self.crop_form.active_rect()
        self.crop_view.set_crop(rect)
        base = rect or full_rect(self.original)
        self.resize_form.set_base_size(base.w, base.h)
        self._schedule_preview()

    def _schedule_preview(self) -> None:
        self._preview_timer.start()

    def _update_preview(self) -> None:
        edit = self.current_edit()
        result = apply_edit(self.original, edit)
        self.result_view.set_pixmap(pil_to_pixmap(result))
        ow, oh = self.original.size
        if edit is None:
            self.result_info.setText(f"{ow} × {oh} px (unchanged)")
        else:
            self.result_info.setText(f"{result.width} × {result.height} px (original {ow} × {oh})")

    def _trim(self) -> None:
        bounds = alpha_bounds(self.original)
        if bounds is None:
            QMessageBox.information(self, APP_NAME, "This sprite is fully transparent; there is nothing to trim to.")
            return
        self.crop_form.set_rect(bounds)

    def _reset(self) -> None:
        self.crop_form.set_rect(full_rect(self.original), activate=False)
        self.crop_form.setChecked(False)
        self.resize_form.set_state(None, self.resize_form.resample())

    def _save_result(self) -> None:
        file_dialogs.save_image_as(self, self.current_result(), self.name)

    def _accept(self) -> None:
        self.edit = self.current_edit()
        self.accept()

    def keyPressEvent(self, e):
        # Enter inside a spin box should commit the value, not close the dialog.
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and self.focusWidget() is not None \
                and self.focusWidget().inherits("QAbstractSpinBox"):
            self.focusWidget().clearFocus()
            return
        super().keyPressEvent(e)
