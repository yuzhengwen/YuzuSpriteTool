"""Application startup."""
from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import APP_ID, APP_NAME
from .core import is_image_file
from .resources import ICON_PATH
from .ui.main_window import MainWindow
from .ui.theme import apply_theme


def _set_windows_app_id() -> None:
    """Give the process its own taskbar identity so Windows shows our icon, not Python's."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)


def create_app(argv: list[str]) -> QApplication:
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))
    apply_theme(app)
    return app


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    _set_windows_app_id()
    app = create_app(argv)
    window = MainWindow()
    window.show()
    # Opening an image with the app (or dragging it onto the exe) loads it in the Unpack tab.
    images = [a for a in argv[1:] if is_image_file(a)]
    if images:
        window.unpack.load_sheet(images[0])
    return app.exec()
