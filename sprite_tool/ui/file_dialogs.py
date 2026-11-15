"""File pickers and saving images to disk, shared by both tabs."""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from .. import APP_NAME
from ..core import IMAGE_EXTS, is_image_file
from . import prefs

IMAGE_FILTER = (
    "Images (" + " ".join(f"*{ext}" for ext in sorted(IMAGE_EXTS)) + ");;All files (*)"
)
PNG_FILTER = "PNG image (*.png)"


def dropped_image_paths(urls) -> list[str]:
    """Image files from dropped URLs. Dropped folders contribute their images, sorted."""
    out: list[str] = []
    for url in urls:
        if not url.isLocalFile():
            continue
        p = Path(url.toLocalFile())
        if p.is_dir():
            out += sorted(str(c) for c in p.iterdir() if is_image_file(c))
        elif is_image_file(p):
            out.append(str(p))
    return out


def ask_open_image(parent: QWidget, title: str) -> str | None:
    path, _ = QFileDialog.getOpenFileName(parent, title, prefs.last_dir(), IMAGE_FILTER)
    return path or None


def ask_open_images(parent: QWidget, title: str) -> list[str]:
    paths, _ = QFileDialog.getOpenFileNames(parent, title, prefs.last_dir(), IMAGE_FILTER)
    return paths


def ask_save_png(parent: QWidget, title: str, default_name: str) -> str | None:
    """Ask for a .png path (extension added if missing). Remembers the folder."""
    default = str(Path(prefs.last_dir()) / f"{default_name}.png")
    path, _ = QFileDialog.getSaveFileName(parent, title, default, PNG_FILTER)
    if not path:
        return None
    if not path.lower().endswith(".png"):
        path += ".png"
    prefs.remember_dir(path)
    return path


def save_image_as(parent: QWidget, img: Image.Image, default_name: str) -> str | None:
    """Ask where to save one image, then save it. Returns the path, or None if cancelled."""
    path = ask_save_png(parent, "Save sprite", default_name)
    if path:
        img.save(path)
    return path


def save_images_to_folder(parent: QWidget, items: list[tuple[str, Image.Image]]) -> tuple[int, str] | None:
    """Ask for a folder and save each (name, image) as name.png.

    Asks once before overwriting existing files. Returns (saved count, folder), or None if cancelled.
    """
    folder = QFileDialog.getExistingDirectory(parent, f"Choose a folder for {len(items)} sprites", prefs.last_dir())
    if not folder:
        return None
    targets = [(Path(folder) / f"{name}.png", img) for name, img in items]
    clashes = sum(1 for p, _ in targets if p.exists())
    if clashes:
        answer = QMessageBox.question(
            parent, APP_NAME,
            f"{clashes} of these files already exist in that folder.\nOverwrite them?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.No)
        if answer == QMessageBox.Cancel:
            return None
        if answer == QMessageBox.No:
            targets = [(p, img) for p, img in targets if not p.exists()]
    for p, img in targets:
        img.save(p)
    prefs.remember_dir(folder)
    return len(targets), folder
