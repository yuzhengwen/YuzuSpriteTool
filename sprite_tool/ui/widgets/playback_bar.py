"""Transport controls: first / previous / play-pause / next / last, speed and loop mode."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from ...core import LOOP, ONCE, PING_PONG
from ...core.animation import MAX_FPS, MIN_FPS
from .factory import spin_box
from .transport_icons import FIRST, LAST, NEXT, PAUSE, PLAY, PREVIOUS, transport_icon

DEFAULT_FPS = 12
MODE_CHOICES = (("Loop", LOOP), ("Ping-pong", PING_PONG), ("Play once", ONCE))
ICON_SIZE = QSize(18, 18)


class PlaybackBar(QWidget):
    playToggled = Signal()
    firstRequested = Signal()
    previousRequested = Signal()
    nextRequested = Signal()
    lastRequested = Signal()
    fpsChanged = Signal(int)

    def __init__(self):
        super().__init__()
        self._play_icon, self._pause_icon = transport_icon(PLAY), transport_icon(PAUSE)
        self.first_btn = self._transport(FIRST, "First frame (Home)", self.firstRequested)
        self.prev_btn = self._transport(PREVIOUS, "Previous frame (←)", self.previousRequested)
        self.play_btn = self._transport(PLAY, "Play / pause (Space)", self.playToggled)
        self.play_btn.setCheckable(True)   # shown pressed while playing; set_playing() keeps it in sync
        self.next_btn = self._transport(NEXT, "Next frame (→)", self.nextRequested)
        self.last_btn = self._transport(LAST, "Last frame (End)", self.lastRequested)

        self.fps = spin_box(MIN_FPS, MAX_FPS, DEFAULT_FPS, suffix=" fps")
        self.fps_slider = QSlider(Qt.Horizontal)
        self.fps_slider.setRange(MIN_FPS, 60)
        self.fps_slider.setValue(DEFAULT_FPS)
        self.fps_slider.setFixedWidth(120)
        self.fps_slider.valueChanged.connect(self.fps.setValue)
        self.fps.valueChanged.connect(self._on_fps)

        self.mode = QComboBox()
        for label, key in MODE_CHOICES:
            self.mode.addItem(label, key)

        self.frame_label = QLabel("")
        self.frame_label.setMinimumWidth(110)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        for b in (self.first_btn, self.prev_btn, self.play_btn, self.next_btn, self.last_btn):
            lay.addWidget(b)
        lay.addSpacing(10)
        lay.addWidget(self.frame_label)
        lay.addStretch()
        lay.addWidget(QLabel("Speed"))
        lay.addWidget(self.fps_slider)
        lay.addWidget(self.fps)
        lay.addSpacing(8)
        lay.addWidget(self.mode)

    def _transport(self, kind: str, tip: str, signal) -> QPushButton:
        b = QPushButton()
        b.setIcon(transport_icon(kind))
        b.setIconSize(ICON_SIZE)
        b.setObjectName("transport")
        b.setToolTip(tip)
        b.setFocusPolicy(Qt.NoFocus)   # keep Space for play/pause, not "press focused button"
        b.clicked.connect(signal)
        return b

    def _on_fps(self, value: int) -> None:
        self.fps_slider.blockSignals(True)
        self.fps_slider.setValue(min(value, self.fps_slider.maximum()))
        self.fps_slider.blockSignals(False)
        self.fpsChanged.emit(value)

    # ------------------------------------------------------------ state shown
    def set_playing(self, playing: bool) -> None:
        self.play_btn.setChecked(playing)
        self.play_btn.setIcon(self._pause_icon if playing else self._play_icon)

    def set_position(self, index: int, count: int) -> None:
        self.frame_label.setText(f"Frame {index + 1} / {count}" if count else "No frames")

    def set_enabled_for(self, count: int) -> None:
        for b in (self.first_btn, self.prev_btn, self.play_btn, self.next_btn, self.last_btn):
            b.setEnabled(count > 0)

    def playback_mode(self) -> str:
        return self.mode.currentData()
