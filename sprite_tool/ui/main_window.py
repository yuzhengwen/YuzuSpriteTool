"""Top-level window: hosts the Unpack and Pack tabs and wires them together."""
from __future__ import annotations

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QTabWidget

from .. import APP_NAME
from . import prefs
from .tabs import PackTab, UnpackTab

DEFAULT_SIZE = (1360, 860)
STATUS_TIMEOUT_MS = 6000


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)

        self.unpack = UnpackTab()
        self.pack = PackTab()
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)   # no light line under the tabs
        self.tabs.addTab(self.unpack, "Unpack  (slice a sheet)")
        self.tabs.addTab(self.pack, "Pack  (build a sheet)")
        self.setCentralWidget(self.tabs)

        for tab in (self.unpack, self.pack):
            tab.status.connect(self._show_status)
        self.unpack.sendToPack.connect(self._send_to_pack)
        self.statusBar().showMessage("Drop a sprite sheet on the left to start slicing.")

        open_action = QAction(self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_for_current_tab)
        self.addAction(open_action)

        self._restore_state()

    def _show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, STATUS_TIMEOUT_MS)

    def _open_for_current_tab(self) -> None:
        if self.tabs.currentWidget() is self.unpack:
            self.unpack.open_dialog()
        else:
            self.pack.add_dialog()

    def _send_to_pack(self, items) -> None:
        self.pack.add_images(items)
        self.tabs.setCurrentWidget(self.pack)

    def _restore_state(self) -> None:
        geometry = prefs.window_geometry()
        if geometry is None or not self.restoreGeometry(geometry):
            self.resize(*DEFAULT_SIZE)
        self.tabs.setCurrentIndex(prefs.last_tab())

    def closeEvent(self, e):
        prefs.save_window_geometry(self.saveGeometry())
        prefs.save_last_tab(self.tabs.currentIndex())
        super().closeEvent(e)
