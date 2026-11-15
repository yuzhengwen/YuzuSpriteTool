"""Generate assets/icon.ico (a yuzu-orange tile holding a 2x2 sprite grid).

Run by build.bat when the icon is missing. Delete assets/icon.ico to regenerate.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon.ico"


def draw(size: int = 256) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 256
    d.rounded_rectangle((8 * s, 8 * s, 248 * s, 248 * s), radius=52 * s, fill=(255, 176, 46, 255))
    colors = [(255, 98, 98), (88, 200, 125), (90, 145, 255), (190, 105, 255)]
    cell, gap, start = 84 * s, 16 * s, 44 * s
    for i, c in enumerate(colors):
        r, col = divmod(i, 2)
        x0 = start + col * (cell + gap)
        y0 = start + r * (cell + gap)
        d.rounded_rectangle((x0, y0, x0 + cell, y0 + cell), radius=14 * s, fill=(36, 36, 40, 255))
        m = 16 * s
        d.ellipse((x0 + m, y0 + m, x0 + cell - m, y0 + cell - m), fill=c + (255,))
    return img


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    draw(256).save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
