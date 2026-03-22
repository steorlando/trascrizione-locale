#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


PROJECT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_DIR / "assets"
MASTER_PNG = ASSETS_DIR / "app_icon.png"
ICNS_PATH = ASSETS_DIR / "app_icon.icns"
ICNS_SIZES = [(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)]


def lerp_channel(start: int, end: int, t: float) -> int:
    return round(start + (end - start) * t)


def gradient_color(t: float) -> tuple[int, int, int]:
    top = (245, 236, 219)
    middle = (236, 145, 98)
    bottom = (177, 76, 49)
    if t < 0.55:
        mix = t / 0.55
        return tuple(lerp_channel(a, b, mix) for a, b in zip(top, middle))
    mix = (t - 0.55) / 0.45
    return tuple(lerp_channel(a, b, mix) for a, b in zip(middle, bottom))


def create_background(size: int) -> Image.Image:
    gradient = Image.new("RGBA", (size, size))
    pixels = gradient.load()
    for y in range(size):
        for x in range(size):
            mix = min(1.0, max(0.0, (x * 0.35 + y * 0.95) / (size * 1.2)))
            color = gradient_color(mix)
            pixels[x, y] = (*color, 255)

    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (86, 98, size - 70, size - 54),
        radius=230,
        fill=(41, 20, 12, 110),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(42))

    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((72, 72, size - 72, size - 72), radius=220, fill=255)

    card = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    card.alpha_composite(shadow)
    card.paste(gradient, (0, 0), mask)

    highlight = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    highlight_draw = ImageDraw.Draw(highlight)
    highlight_draw.ellipse((120, 90, 700, 520), fill=(255, 255, 255, 95))
    highlight = highlight.filter(ImageFilter.GaussianBlur(80))
    card.alpha_composite(highlight)

    vignette = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    vignette_draw = ImageDraw.Draw(vignette)
    vignette_draw.ellipse((250, 420, 1120, 1180), fill=(80, 20, 8, 80))
    vignette = vignette.filter(ImageFilter.GaussianBlur(70))
    card.alpha_composite(vignette)

    return card


def draw_document(img: Image.Image) -> None:
    size = img.width
    canvas = ImageDraw.Draw(img)

    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((268, 174, 758, 842), radius=116, fill=(63, 24, 14, 105))
    shadow_draw.ellipse((316, 724, 736, 892), fill=(63, 24, 14, 75))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    img.alpha_composite(shadow)

    panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(panel)
    panel_draw.rounded_rectangle(
        (286, 154, 738, 822),
        radius=108,
        fill=(251, 246, 237, 255),
        outline=(244, 225, 204, 255),
        width=6,
    )
    panel_draw.rounded_rectangle((316, 218, 356, 760), radius=20, fill=(199, 90, 56, 255))
    panel_draw.ellipse((344, 248, 410, 314), fill=(239, 111, 67, 255))
    panel_draw.ellipse((358, 262, 396, 300), fill=(255, 224, 204, 255))

    fold = [(646, 154), (738, 154), (738, 246)]
    panel_draw.polygon(fold, fill=(244, 230, 214, 255))
    panel_draw.line([(646, 154), (646, 246), (738, 246)], fill=(232, 209, 189, 255), width=6)
    img.alpha_composite(panel)

    waveform = ImageDraw.Draw(img)
    wave_color = (47, 69, 77, 255)
    base_y = 466
    centers = [432, 494, 556, 618]
    heights = [108, 178, 126, 84]
    for center, height in zip(centers, heights):
        top = base_y - height // 2
        bottom = base_y + height // 2
        waveform.rounded_rectangle((center - 18, top, center + 18, bottom), radius=18, fill=wave_color)

    waveform.rounded_rectangle((412, 608, 664, 644), radius=18, fill=(111, 123, 130, 255))
    waveform.rounded_rectangle((412, 674, 632, 706), radius=16, fill=(163, 172, 177, 255))
    waveform.rounded_rectangle((412, 732, 592, 760), radius=14, fill=(198, 205, 209, 255))

    ring = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(ring)
    ring_draw.arc((206, 226, size - 206, size - 182), start=204, end=338, fill=(255, 245, 235, 120), width=18)
    ring_draw.arc((244, 264, size - 244, size - 220), start=208, end=334, fill=(122, 34, 18, 78), width=12)
    ring = ring.filter(ImageFilter.GaussianBlur(1))
    img.alpha_composite(ring)


def build_master_icon(size: int = 1024) -> Image.Image:
    icon = create_background(size)
    draw_document(icon)
    return icon


def main() -> int:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    master_icon = build_master_icon()
    master_icon.save(MASTER_PNG)
    master_icon.save(ICNS_PATH, format="ICNS", sizes=ICNS_SIZES)
    print(f"Master PNG: {MASTER_PNG}")
    print(f"ICNS: {ICNS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
