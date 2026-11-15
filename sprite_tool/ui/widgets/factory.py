"""Small constructors for consistently styled basic widgets."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSpinBox


def spin_box(lo: int, hi: int, value: int, *, suffix: str = " px", special: str | None = None) -> QSpinBox:
    """Integer spin box. `special` is shown instead of the minimum value (e.g. "Auto")."""
    sb = QSpinBox()
    sb.setRange(lo, hi)
    sb.setValue(value)
    sb.setSuffix(suffix)
    sb.setAccelerated(True)
    if special:
        sb.setSpecialValueText(special)
    return sb


def pane_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("paneTitle")
    return lbl


def hint_label(text: str = "", wrap: bool = True) -> QLabel:
    """Muted secondary text."""
    lbl = QLabel(text)
    lbl.setObjectName("hint")
    lbl.setWordWrap(wrap)
    return lbl


def separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setObjectName("separator")
    return line


def primary_button(text: str) -> QPushButton:
    """Accent-colored button for a pane's main action."""
    btn = QPushButton(text)
    btn.setObjectName("primary")
    return btn
