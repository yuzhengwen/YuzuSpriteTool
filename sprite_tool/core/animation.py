"""Animation playback rules and frame preparation (no timers or UI here)."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from .packing import ALIGN_CENTER, align_offset

LOOP = "loop"            # 0 1 2 0 1 2 ...
PING_PONG = "pingpong"   # 0 1 2 1 0 1 2 ...
ONCE = "once"            # 0 1 2, then stop

MIN_FPS, MAX_FPS = 1, 120


@dataclass(frozen=True)
class Step:
    index: int
    direction: int     # +1 forward, -1 backward (ping-pong)
    finished: bool     # True when a play-once animation reached its end


def next_frame(index: int, count: int, direction: int, mode: str) -> Step:
    """The frame after `index` for the given playback mode."""
    if count <= 1:
        return Step(0, 1, mode == ONCE)
    if mode == PING_PONG:
        nxt = index + direction
        if nxt >= count:
            return Step(count - 2, -1, False)
        if nxt < 0:
            return Step(1, 1, False)
        return Step(nxt, direction, False)
    if mode == ONCE:
        if index + 1 >= count:
            return Step(count - 1, 1, True)
        return Step(index + 1, 1, False)
    return Step((index + 1) % count, 1, False)


def frame_interval_ms(fps: float) -> int:
    fps = min(max(fps, MIN_FPS), MAX_FPS)
    return max(1, round(1000 / fps))


def compose_frames(images: list[Image.Image], align: str = ALIGN_CENTER) -> list[Image.Image]:
    """Place every frame on a shared canvas (the largest frame size).

    Frames of different sizes (e.g. trimmed sprites) then stay anchored instead of
    jumping around as the animation plays.
    """
    if not images:
        return []
    w = max(im.width for im in images)
    h = max(im.height for im in images)
    if all(im.size == (w, h) for im in images):
        return list(images)
    frames = []
    for im in images:
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.alpha_composite(im, align_offset(align, w, h, im.width, im.height))
        frames.append(canvas)
    return frames
