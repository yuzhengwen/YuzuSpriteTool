# PyInstaller build recipe for Yuzu Sprite Tool. Used by build.bat.
# Produces a single-file, windowed executable: dist\YuzuSpriteTool.exe

# Qt modules the app never imports. Excluding them keeps the exe much smaller.
EXCLUDES = [
    "tkinter",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuick3D",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DExtras",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtBluetooth", "PySide6.QtPositioning", "PySide6.QtLocation",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSvg", "PySide6.QtSvgWidgets",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("assets/icon.ico", "assets")],
    hiddenimports=[],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="YuzuSpriteTool",
    icon="assets/icon.ico",
    console=False,          # no terminal window behind the app
    upx=False,
    debug=False,
    strip=False,
    runtime_tmpdir=None,
)
