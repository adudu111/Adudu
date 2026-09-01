"""Generate resources/icon.ico (a simple, original CyberGlossary app icon).

Run once during development:  python scripts/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "resources" / "icon.ico"

ACCENT = (79, 140, 255, 255)
WHITE = (255, 255, 255, 255)
SIZE = 256


def _render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = size * 0.04
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=size * 0.2,
        fill=ACCENT,
    )
    # A simple open-book / glossary mark: three horizontal white bars (a page).
    bar = size * 0.12
    gap = size * 0.16
    left = size * 0.26
    right = size * 0.74
    top = size * 0.26
    for i in range(3):
        y0 = top + i * (bar + gap)
        draw.rounded_rectangle(
            [left, y0, right, y0 + bar],
            radius=bar // 2,
            fill=WHITE,
        )
    return img


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    image = _render(SIZE)
    image.save(OUT, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
