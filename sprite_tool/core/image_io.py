"""Loading images and recognising image files."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tga", ".tif", ".tiff"})


def is_image_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTS


def load_rgba(path: str | Path) -> Image.Image:
    """Open any supported image as RGBA, fully loaded so the file handle is released."""
    with Image.open(path) as im:
        im.load()
        return im.convert("RGBA")


def is_fully_transparent(img: Image.Image) -> bool:
    return img.getchannel("A").getbbox() is None
