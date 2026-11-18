"""Colors, palette and stylesheet. Every visual constant lives here."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# -- brand / overlay colors
ACCENT = QColor(255, 176, 46)          # yuzu orange: grid lines, primary buttons
SELECTION = QColor(90, 170, 255)       # selected cells on a sheet
ERROR_HEX = "#ff7a7a"

# -- surfaces
WINDOW = QColor(37, 37, 41)
VIEW_BG = QColor(30, 30, 33)           # behind images
CHECKER_LIGHT = QColor(58, 58, 62)
CHECKER_DARK = QColor(44, 44, 48)
PLACEHOLDER_BORDER = QColor(110, 110, 118)
PLACEHOLDER_TEXT = QColor(160, 160, 168)
ICON_INK = QColor(30, 30, 33)          # glyphs drawn on accent-colored buttons
SWATCH_NONE = QColor(70, 70, 76)       # color swatch when no color applies

STYLESHEET = """
QWidget { font-size: 10pt; }
QLabel#paneTitle { font-size: 13pt; font-weight: 600; color: #f2f2f2; }
QLabel#hint { color: #9a9aa3; }

QGroupBox { border: 1px solid #3a3a40; border-radius: 8px; margin-top: 14px; padding: 10px 8px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #ffb02e; font-weight: 600; }
QFrame#separator { color: #3a3a40; }

QPushButton { padding: 5px 12px; border-radius: 6px; background: #3a3a40; border: 1px solid #4a4a52; }
QPushButton:hover { background: #46464e; }
QPushButton:pressed { background: #2f2f35; }
QPushButton:disabled { color: #6c6c74; background: #303035; border-color: #38383e; }
QPushButton#primary { background: #ffb02e; color: #1e1e21; border: 1px solid #ffb02e; font-weight: 600; }
QPushButton#primary:hover { background: #ffc254; }
QPushButton#primary:disabled { background: #5a4a2c; color: #8a7a5c; border-color: #5a4a2c; }
/* Segmented control: joined toggle buttons, rounded only on the outer ends. */
QPushButton#segment, QPushButton#segmentFirst, QPushButton#segmentLast { padding: 5px 16px; }
QPushButton#segment { border-radius: 0; }
QPushButton#segmentFirst { border-top-right-radius: 0; border-bottom-right-radius: 0; }
QPushButton#segmentLast { border-top-left-radius: 0; border-bottom-left-radius: 0; }
QPushButton#segment:checked, QPushButton#segmentFirst:checked, QPushButton#segmentLast:checked {
    background: #ffb02e; color: #1e1e21; border-color: #ffb02e; font-weight: 600; }
QPushButton#transport { padding: 4px 8px; min-width: 34px; font-size: 11pt; }
QPushButton#transport:checked { background: #ffb02e; color: #1e1e21; border-color: #ffb02e; }

QListWidget { background: #232327; border: 1px solid #3a3a40; border-radius: 8px; padding: 4px; }
QListWidget::item { border-radius: 6px; padding: 2px; }
QListWidget::item:hover { background: #303036; }
QListWidget::item:selected { background: #2b4a6e; color: white; }

/* Tabs: no base line and an explicit bar background, so nothing light shows
   through the gaps beside the rounded tab corners. */
QTabWidget::pane { border: none; top: 0px; }
QTabWidget::tab-bar { left: 8px; }
QTabBar { background: #252529; border: none; qproperty-drawBase: 0; }
QTabBar::tab { padding: 8px 22px; margin: 6px 4px 0 0; border: none; background: #2a2a2f;
               border-top-left-radius: 8px; border-top-right-radius: 8px;
               color: #b8b8c0; font-weight: 600; }
QTabBar::tab:hover:!selected { background: #323238; }
QTabBar::tab:selected { background: #3a3a40; color: #ffb02e; }

QSplitter::handle { background: #2a2a2f; width: 4px; }
QComboBox, QLineEdit { padding: 3px 6px; border-radius: 5px; background: #2a2a2f; border: 1px solid #44444b; }
QSpinBox { padding: 2px 4px; }
QStatusBar { color: #9a9aa3; }
"""


def dark_palette() -> QPalette:
    p = QPalette()
    text = QColor(225, 225, 230)
    p.setColor(QPalette.Window, WINDOW)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, QColor(35, 35, 39))
    p.setColor(QPalette.AlternateBase, QColor(45, 45, 50))
    p.setColor(QPalette.ToolTipBase, QColor(50, 50, 56))
    p.setColor(QPalette.ToolTipText, QColor(230, 230, 235))
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, QColor(58, 58, 64))
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.BrightText, QColor(255, 255, 255))
    p.setColor(QPalette.Highlight, QColor(43, 74, 110))
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.Link, ACCENT)
    p.setColor(QPalette.PlaceholderText, QColor(120, 120, 128))
    # Bevel/frame roles. Fusion draws edges and tab-bar lines with these; left at
    # their light-theme defaults they show up as stray white lines.
    p.setColor(QPalette.Light, QColor(64, 64, 70))
    p.setColor(QPalette.Midlight, QColor(54, 54, 60))
    p.setColor(QPalette.Mid, QColor(42, 42, 47))
    p.setColor(QPalette.Dark, QColor(28, 28, 31))
    p.setColor(QPalette.Shadow, QColor(18, 18, 20))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(110, 110, 118))
    return p


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setStyleSheet(STYLESHEET)


def error_html(message: str) -> str:
    """Rich text for showing an error inside an info label."""
    return f"<span style='color:{ERROR_HEX}'>{message}</span>"
