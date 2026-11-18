"""Animate tab: pick frames (left, from sprites or a sheet) and preview the animation (right)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from ...core import (
    ALIGN_BOTTOM, ALIGN_CENTER, ALIGN_TOP_LEFT, ONCE, compose_frames, frame_interval_ms, next_frame,
)
from ..panels import SheetSlicerPanel, SpriteListPanel
from ..qt_image import pil_to_pixmap
from ..widgets import FrameStrip, ImageView, PlaybackBar, SegmentedControl, ZoomBar, hint_label, pane_title

SOURCE_SPRITES, SOURCE_SHEET = 0, 1
REBUILD_DELAY_MS = 80
ALIGN_CHOICES = (("Center", ALIGN_CENTER), ("Bottom center", ALIGN_BOTTOM), ("Top-left", ALIGN_TOP_LEFT))
HINT = "Click a frame to show it · double-click to play from it · Space plays/pauses · ←/→ step"


class AnimateTab(QWidget):
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self._frames: list[QPixmap] = []
        self._index = 0
        self._direction = 1

        self._play_timer = QTimer(self)
        self._play_timer.setTimerType(Qt.PreciseTimer)
        self._play_timer.timeout.connect(self._tick)
        self._rebuild_timer = QTimer(self, singleShot=True, interval=REBUILD_DELAY_MS)
        self._rebuild_timer.timeout.connect(self.rebuild_frames)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_source_pane())
        splitter.addWidget(self._build_preview_pane())
        splitter.setSizes([560, 760])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(splitter)
        self._install_shortcuts()
        self._show_empty()

    # ================================================================ layout
    def _build_source_pane(self) -> QWidget:
        self.source_switch = SegmentedControl(["Sprites", "Sprite sheet"], current=SOURCE_SHEET)
        self.source_switch.changed.connect(self._on_source_changed)
        switch_row = QHBoxLayout()
        switch_row.addWidget(QLabel("Frames from"))
        switch_row.addWidget(self.source_switch)
        switch_row.addStretch()

        self.sprite_list = SpriteListPanel("Frames (in order)")
        self.sprite_list.changed.connect(lambda: self._source_changed(SOURCE_SPRITES))
        self.sprite_list.status.connect(self.status)

        self.slicer = SheetSlicerPanel()
        self.slicer.sliced.connect(lambda: self._source_changed(SOURCE_SHEET))
        self.slicer.spriteClicked.connect(self._on_sheet_clicked)
        self.slicer.status.connect(self.status)

        self.sources = QStackedWidget()
        self.sources.insertWidget(SOURCE_SPRITES, self.sprite_list)
        self.sources.insertWidget(SOURCE_SHEET, self.slicer)
        self.sources.setCurrentIndex(SOURCE_SHEET)

        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.addLayout(switch_row)
        lay.addWidget(self.sources, 1)
        return pane

    def _build_preview_pane(self) -> QWidget:
        self.view = ImageView("Load a sprite sheet or add sprites on the left\nto preview the animation",
                              accept_drops=False)
        self.info = hint_label(wrap=False)
        header = QHBoxLayout()
        header.addWidget(pane_title("Animation preview"))
        header.addWidget(self.info)
        header.addStretch()
        header.addWidget(ZoomBar(self.view))

        self.align = QComboBox()
        for label, key in ALIGN_CHOICES:
            self.align.addItem(label, key)
        self.align.setToolTip("Where smaller frames sit when frames have different sizes.")
        self.align.currentIndexChanged.connect(self._schedule_rebuild)
        align_row = QHBoxLayout()
        align_row.addStretch()
        align_row.addWidget(QLabel("Align frames"))
        align_row.addWidget(self.align)

        self.controls = PlaybackBar()
        self.controls.playToggled.connect(self.toggle_play)
        self.controls.firstRequested.connect(lambda: self.show_frame(0, pause=True))
        self.controls.lastRequested.connect(lambda: self.show_frame(len(self._frames) - 1, pause=True))
        self.controls.previousRequested.connect(lambda: self.step(-1))
        self.controls.nextRequested.connect(lambda: self.step(1))
        self.controls.fpsChanged.connect(self._on_fps_changed)

        self.strip = FrameStrip()
        self.strip.frameChosen.connect(lambda i: self.show_frame(i, pause=True))
        self.strip.frameActivated.connect(self.play_from)

        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(6, 0, 0, 0)
        lay.addLayout(header)
        lay.addWidget(self.view, 1)
        lay.addLayout(align_row)
        lay.addWidget(self.controls)
        lay.addWidget(self.strip)
        lay.addWidget(hint_label(HINT, wrap=False))
        return pane

    def _install_shortcuts(self) -> None:
        bindings = (
            (Qt.Key_Left, lambda: self.step(-1)),
            (Qt.Key_Right, lambda: self.step(1)),
            (Qt.Key_Home, lambda: self.show_frame(0, pause=True)),
            (Qt.Key_End, lambda: self.show_frame(len(self._frames) - 1, pause=True)),
        )
        for key, action in bindings:
            # Bound to the preview side only, so arrows still work in the lists and spin boxes on the left.
            for target in (self.view, self.strip):
                sc = QShortcut(QKeySequence(key), target)
                sc.setContext(Qt.WidgetShortcut)
                sc.activated.connect(action)
        # Space works anywhere in the tab (text and number fields still receive their own spaces).
        space = QShortcut(QKeySequence(Qt.Key_Space), self)
        space.setContext(Qt.WidgetWithChildrenShortcut)
        space.activated.connect(self.toggle_play)

    def open_dialog(self) -> None:
        """Ctrl+O: open a sheet or add sprites, depending on the current source."""
        if self.source == SOURCE_SHEET:
            self.slicer.open_dialog()
        else:
            self.sprite_list.add_dialog()

    # ================================================================ frame source
    @property
    def source(self) -> int:
        return self.sources.currentIndex()

    def _on_source_changed(self, index: int) -> None:
        self.sources.setCurrentIndex(index)
        self.pause()
        self._schedule_rebuild()

    def _source_changed(self, which: int) -> None:
        if which == self.source:
            self._schedule_rebuild()

    def _source_images(self):
        if self.source == SOURCE_SHEET:
            return [s.image for s in self.slicer.sprites]
        return [e.image for e in self.sprite_list.entries()]

    def _schedule_rebuild(self) -> None:
        self._rebuild_timer.start()

    def rebuild_frames(self) -> None:
        """Recreate the frames from the current source, keeping the position when possible."""
        images = compose_frames(self._source_images(), self.align.currentData())
        self._frames = [pil_to_pixmap(im) for im in images]
        self.strip.set_frames(self._frames)
        self.controls.set_enabled_for(len(self._frames))
        if not self._frames:
            self._show_empty()
            return
        w, h = images[0].size
        self.info.setText(f"{len(images)} frames · {w} × {h} px")
        self._direction = 1
        self.show_frame(min(self._index, len(self._frames) - 1))

    def _show_empty(self) -> None:
        self.pause()
        self._frames = []
        self._index = 0
        self.view.clear_image()
        self.info.setText("")
        self.controls.set_position(0, 0)
        self.controls.set_enabled_for(0)
        self.slicer.highlight([])

    # ================================================================ playback
    @property
    def playing(self) -> bool:
        return self._play_timer.isActive()

    @property
    def current_index(self) -> int:
        return self._index

    def show_frame(self, index: int, pause: bool = False) -> None:
        if pause:
            self.pause()
        if not self._frames:
            return
        self._index = max(0, min(index, len(self._frames) - 1))
        self.view.update_pixmap(self._frames[self._index])
        self.strip.set_current(self._index)
        self.controls.set_position(self._index, len(self._frames))
        if self.source == SOURCE_SHEET:
            self.slicer.highlight([self._index])

    def step(self, delta: int) -> None:
        if self._frames:
            self.show_frame((self._index + delta) % len(self._frames), pause=True)

    def play(self) -> None:
        if len(self._frames) < 2:
            return
        at_end = self._index == len(self._frames) - 1
        if self.controls.playback_mode() == ONCE and at_end:
            self.show_frame(0)   # replaying a finished one-shot starts over
        self._direction = 1
        self._play_timer.start(frame_interval_ms(self.controls.fps.value()))
        self.controls.set_playing(True)

    def pause(self) -> None:
        self._play_timer.stop()
        self.controls.set_playing(False)

    def toggle_play(self) -> None:
        if self.playing:
            self.pause()
        else:
            self.play()

    def play_from(self, index: int) -> None:
        self.show_frame(index)
        self.play()

    def _tick(self) -> None:
        nxt = next_frame(self._index, len(self._frames), self._direction, self.controls.playback_mode())
        self._direction = nxt.direction
        self.show_frame(nxt.index)
        if nxt.finished:
            self.pause()

    def _on_fps_changed(self, fps: int) -> None:
        if self.playing:
            self._play_timer.setInterval(frame_interval_ms(fps))

    def _on_sheet_clicked(self, index: int, _modifiers) -> None:
        if index >= 0:
            self.show_frame(index, pause=True)

    def hideEvent(self, e):
        self.pause()   # don't keep animating in a tab nobody is looking at
        super().hideEvent(e)
