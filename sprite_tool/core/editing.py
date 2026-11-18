"""Non-destructive sprite edits: crop, then resize.

An edit is a description, applied to the untouched original each time. Reverting
is just dropping the edit, and re-editing never stacks quality loss.
"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from .geometry import Rect

MAX_EDIT_SIZE = 16384

RESAMPLE_NEAREST = "nearest"
RESAMPLE_BILINEAR = "bilinear"
RESAMPLE_BICUBIC = "bicubic"
RESAMPLE_LANCZOS = "lanczos"

RESAMPLE_FILTERS = {
    RESAMPLE_NEAREST: Image.Resampling.NEAREST,     # crisp, for pixel art
    RESAMPLE_BILINEAR: Image.Resampling.BILINEAR,
    RESAMPLE_BICUBIC: Image.Resampling.BICUBIC,
    RESAMPLE_LANCZOS: Image.Resampling.LANCZOS,     # smoothest downscaling
}


@dataclass(frozen=True)
class SpriteEdit:
    crop: Rect | None = None                  # area of the original to keep
    size: tuple[int, int] | None = None       # final width/height after cropping
    resample: str = RESAMPLE_NEAREST

    @property
    def is_identity(self) -> bool:
        return self.crop is None and self.size is None


def full_rect(img: Image.Image) -> Rect:
    return Rect(0, 0, img.width, img.height)


def clamp_rect(rect: Rect, img_w: int, img_h: int) -> Rect:
    """Keep a rectangle inside the image and at least 1 x 1 px."""
    x = min(max(0, rect.x), img_w - 1)
    y = min(max(0, rect.y), img_h - 1)
    w = min(max(1, rect.w), img_w - x)
    h = min(max(1, rect.h), img_h - y)
    return Rect(x, y, w, h)


def alpha_bounds(img: Image.Image) -> Rect | None:
    """Smallest rectangle holding every visible pixel, or None if fully transparent."""
    bbox = img.getchannel("A").getbbox()
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    return Rect(x0, y0, x1 - x0, y1 - y0)


def cropped_size(img: Image.Image, edit: SpriteEdit) -> tuple[int, int]:
    return (edit.crop.w, edit.crop.h) if edit.crop else img.size


def result_size(img: Image.Image, edit: SpriteEdit) -> tuple[int, int]:
    return edit.size or cropped_size(img, edit)


def normalize_edit(img: Image.Image, edit: SpriteEdit) -> SpriteEdit | None:
    """Clamp values, drop parts that change nothing, and return None for a no-op edit."""
    crop = clamp_rect(edit.crop, img.width, img.height) if edit.crop else None
    if crop == full_rect(img):
        crop = None
    size = None
    if edit.size:
        w, h = (min(max(1, v), MAX_EDIT_SIZE) for v in edit.size)
        base = (crop.w, crop.h) if crop else img.size
        size = None if (w, h) == base else (w, h)
    resample = edit.resample if edit.resample in RESAMPLE_FILTERS else RESAMPLE_NEAREST
    result = SpriteEdit(crop, size, resample)
    return None if result.is_identity else result


def apply_edit(img: Image.Image, edit: SpriteEdit | None) -> Image.Image:
    """Return the edited image (the original object itself when there is nothing to do)."""
    if edit is None or edit.is_identity:
        return img
    out = img
    if edit.crop:
        c = edit.crop
        out = out.crop((c.x, c.y, c.x + c.w, c.y + c.h))
    if edit.size and edit.size != out.size:
        out = out.resize(edit.size, RESAMPLE_FILTERS.get(edit.resample, Image.Resampling.NEAREST))
    return out
