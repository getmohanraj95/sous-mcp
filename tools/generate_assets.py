"""Generate the Sous icon set (6 sizes) and the 600x900 carousel image.

    pip install pillow
    python tools/generate_assets.py

Writes to docs/assets/ so GitHub Pages serves the same files addon.json links to.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG = (29, 42, 34)          # basil ink
ACCENT = (180, 83, 28)     # paprika
PAPER = (255, 254, 249)
SAGE = (143, 172, 134)

ICON_SIZES = (72, 64, 88, 126, 180, 241)
OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "assets"


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _rounded_mask(size: int, radius_ratio: float = 0.22) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * radius_ratio), fill=255)
    return mask


def draw_master_icon(size: int = 512) -> Image.Image:
    """A pot with a spoon and steam: flat shapes that stay legible at 64 px."""
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)
    cx = size // 2
    pot_w, pot_h = int(size * 0.64), int(size * 0.38)
    left, top = cx - pot_w // 2, size // 2 - pot_h // 2 + int(size * 0.14)
    draw.rounded_rectangle([left, top, left + pot_w, top + pot_h], radius=int(pot_h * 0.25), fill=ACCENT)

    rim_y = top + int(pot_h * 0.16)
    draw.rounded_rectangle(
        [left - int(size * 0.03), rim_y - int(size * 0.018), left + pot_w + int(size * 0.03), rim_y + int(size * 0.018)],
        radius=int(size * 0.018), fill=PAPER,
    )
    spoon_x, bowl_y, bowl_r = cx + int(size * 0.08), rim_y - int(size * 0.035), int(size * 0.07)
    draw.line([spoon_x, bowl_y, spoon_x - int(size * 0.06), top - int(size * 0.26)], fill=SAGE, width=max(4, size // 28))
    draw.ellipse([spoon_x - bowl_r, bowl_y - bowl_r, spoon_x + bowl_r, bowl_y + bowl_r], fill=SAGE)
    for dx in (-int(size * 0.17), -int(size * 0.05)):
        x0, y0 = cx + dx, top - int(size * 0.05)
        draw.line([x0, y0, x0 + int(size * 0.03), y0 - int(size * 0.09), x0, y0 - int(size * 0.18)],
                  fill=PAPER, width=max(3, size // 45), joint="curve")
    return img


def make_icon(master: Image.Image, size: int) -> Image.Image:
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(master.resize((size, size), Image.LANCZOS), (0, 0), _rounded_mask(size))
    return out


def make_carousel(width: int = 600, height: int = 900) -> Image.Image:
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)
    icon = 240
    img.paste(draw_master_icon(512).resize((icon, icon), Image.LANCZOS), ((width - icon) // 2, 120), _rounded_mask(icon))

    def centred(text: str, y: int, font: ImageFont.ImageFont, fill: tuple[int, int, int]) -> None:
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(((width - (box[2] - box[0])) / 2, y), text, font=font, fill=fill)

    centred("Sous", 410, _font(64), PAPER)
    for i, line in enumerate(("Your AI sous-chef.", "Cook from what's already", "in your kitchen.")):
        centred(line, 510 + i * 44, _font(30), SAGE if i == 0 else PAPER)
    draw.rectangle([0, height - 16, width, height], fill=ACCENT)
    return img


def main() -> None:
    (OUT_DIR / "icons").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "carousel").mkdir(parents=True, exist_ok=True)
    master = draw_master_icon()
    for size in ICON_SIZES:
        make_icon(master, size).save(OUT_DIR / "icons" / f"icon-{size}x{size}.png")
    make_carousel().save(OUT_DIR / "carousel" / "carousel-1.png")
    print(f"Wrote {len(ICON_SIZES)} icons and 1 carousel image to {OUT_DIR}")


if __name__ == "__main__":
    main()
