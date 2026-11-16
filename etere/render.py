"""Dalla matrice del segnale all'immagine 1-bit per l'e-paper 250x122."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H = 250, 122


def render(matrix, clean=0.6, blur=0.0, invert=False, rotate=0):
    m = np.nan_to_num(np.asarray(matrix, float))
    lo, hi = np.percentile(m, [2, 98])
    if hi - lo < 1e-9:
        hi = lo + 1.0
    a = np.clip((m - lo) / (hi - lo), 0, 1)
    img = Image.fromarray((a * 255).astype("uint8"), "L").resize((W, H), Image.BILINEAR)
    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if clean > 0:
        img = img.filter(ImageFilter.MedianFilter(3))
        arr = np.asarray(img, float) / 255.0
        arr = np.clip((arr - 0.5) * (1.0 + clean) + 0.5, 0, 1)
        img = Image.fromarray((arr * 255).astype("uint8"), "L")
    if invert:
        img = ImageOps.invert(img)
    if rotate:
        img = img.rotate(rotate)
    return img.convert("1")  # dithering Floyd-Steinberg


def _font(size):
    for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def message(text, rotate=0):
    img = Image.new("1", (W, H), 1)
    d = ImageDraw.Draw(img)
    f = _font(14)
    lines = text.split("\n")
    y = (H - 18 * len(lines)) // 2
    for ln in lines:
        w = d.textlength(ln, font=f)
        d.text(((W - w) // 2, y), ln, fill=0, font=f)
        y += 18
    return img.rotate(rotate) if rotate else img


def test_pattern(rotate=0):
    img = Image.new("1", (W, H), 1)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W - 1, H - 1), outline=0)
    for i in range(0, 60, 6):
        d.rectangle((4 + i, 4 + i // 3, 4 + i + 3, H - 5 - i // 3), fill=0)
    f = _font(22)
    d.text((84, 30), "etere", fill=0, font=f)
    d.text((84, 62), "display OK", fill=0, font=_font(14))
    return img.rotate(rotate) if rotate else img
