"""Dalla matrice del segnale all'immagine 1-bit per l'e-paper 250x122."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H = 250, 122
VIEWS = ("spettro", "variazioni", "intensita", "mix")
DITHERS = ("floyd", "bayer")

# matrice di Bayer 8x8: dithering "a reticolo", regolare come un'incisione
_BAYER = np.array([
    [0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38], [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21]])


def _norm(m):
    lo, hi = np.percentile(m, [2, 98])
    if hi - lo < 1e-9:
        hi = lo + 1.0
    return np.clip((m - lo) / (hi - lo), 0, 1)


def apply_view(m, view):
    """spettro: il segnale cosi' com'e'.
    variazioni: scarto di ogni riga dalla sua media nel tempo (+ bianco, - nero).
    intensita: quanto cambia, senza segno (fermo = nero, evento = bianco).
    mix: meta' spettro e meta' intensita'."""
    if view == "spettro":
        return m
    dev = m - m.mean(axis=1, keepdims=True)
    if view == "variazioni":
        return dev
    if view == "intensita":
        return np.abs(dev)
    if view == "mix":
        return 0.5 * _norm(m) + 0.5 * _norm(np.abs(dev))
    raise ValueError(f"VIEW sconosciuta: {view} (usa {', '.join(VIEWS)})")


def dither(img, method="floyd"):
    if method == "floyd":
        return img.convert("1")  # Floyd-Steinberg
    if method == "bayer":
        a = np.asarray(img.convert("L"), float) / 255.0
        h, w = a.shape
        t = (np.tile(_BAYER, (h // 8 + 1, w // 8 + 1))[:h, :w] + 0.5) / 64.0
        return Image.fromarray(((a > t) * 255).astype("uint8"), "L").convert("1")
    raise ValueError(f"DITHER sconosciuto: {method} (usa {', '.join(DITHERS)})")


def render(matrix, clean=0.6, blur=0.0, invert=False, rotate=0, view="spettro", method="floyd"):
    m = apply_view(np.nan_to_num(np.asarray(matrix, float)), view)
    a = _norm(m)
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
    return dither(img, method)


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
