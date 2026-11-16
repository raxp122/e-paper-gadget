"""Tarocchi: un mazzo completo di 78 carte (22 arcani maggiori e 56 minori).
Ogni N secondi estrae una carta a caso, dritta o capovolta, e la mostra con
nome e parole chiave. Immagini: Rider-Waite-Smith (1909), pubblico dominio.
"""
import json
import logging
import os
import secrets

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

import render

log = logging.getLogger("etere.tarocchi")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))
CARDS_DIR = os.path.join(DATA, "tarocchi", "cards")
W, H = render.W, render.H
CARD_W, CARD_H = 71, 122           # proporzioni 350x600 delle scansioni
TEXT_X = CARD_W + 7
TEXT_W = W - TEXT_X - 2


def load_deck(path=os.path.join(DATA, "tarocchi.json")):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    deck = []
    for img, num, name, up, rev in d["maggiori"]:
        deck.append({"img": img, "head": f"{num} · Arcano maggiore", "name": name,
                     "up": up, "rev": rev})
    for suit, sname in d["semi"].items():
        for i, (up, rev) in enumerate(d["minori"][suit]):
            rank = d["gradi"][i]
            deck.append({"img": f"{suit}{i + 1:02d}", "head": f"{sname} · Arcano minore",
                         "name": f"{rank} di {sname}", "up": up, "rev": rev})
    return deck


def font(size, bold=False):
    names = (["DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
             if bold else ["DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    from PIL import ImageFont
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            pass
    return render._font(size)


def wrap(draw, text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def card_image(code, reversed_):
    path = os.path.join(CARDS_DIR, code + ".jpg")
    if os.path.exists(path):
        im = Image.open(path).convert("L")
        im = ImageOps.autocontrast(im, cutoff=1)
        im = ImageEnhance.Contrast(im).enhance(1.3)
        im = im.resize((CARD_W, CARD_H), Image.LANCZOS)
        im = ImageEnhance.Sharpness(im).enhance(1.6)
    else:  # immagini non ancora scaricate: segnaposto
        im = Image.new("L", (CARD_W, CARD_H), 255)
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, CARD_W - 1, CARD_H - 1), outline=0)
        d.text((CARD_W // 2 - 4, CARD_H // 2 - 8), "?", fill=0, font=font(16, True))
    if reversed_:
        im = im.rotate(180)
    return render.dither(im, "floyd")


def fit(d, card, reversed_):
    """Sceglie le dimensioni dei caratteri piu' grandi che fanno entrare tutto."""
    words = card["rev"] if reversed_ else card["up"]
    for name_size, kw_size in ((17, 13), (16, 12), (15, 12), (14, 11), (13, 11), (12, 10)):
        fh, fn, fk = font(10), font(name_size, True), font(kw_size)
        name_lines = wrap(d, card["name"], fn, TEXT_W)
        kw_lines = [ln for w in words for ln in wrap(d, "· " + w, fk, TEXT_W)]
        total = 17 + len(name_lines) * (name_size + 3) + (16 if reversed_ else 0) + 4 + len(kw_lines) * (kw_size + 4)
        widest = max(d.textlength(t, font=f) for t, f in
                     [(card["head"], fh)] + [(n, fn) for n in name_lines] + [(k, fk) for k in kw_lines])
        if total <= H and len(name_lines) <= 2 and widest <= TEXT_W:
            break
    return name_size, kw_size, fh, fn, fk, name_lines, kw_lines, total, widest


def draw_card(card, reversed_):
    img = Image.new("1", (W, H), 1)
    img.paste(card_image(card["img"], reversed_), (0, 0))
    d = ImageDraw.Draw(img)
    name_size, kw_size, fh, fn, fk, name_lines, kw_lines, _, _ = fit(d, card, reversed_)
    y = 2
    d.text((TEXT_X, y), card["head"], fill=0, font=fh)
    y += 15
    for ln in name_lines:
        d.text((TEXT_X, y), ln, fill=0, font=fn)
        y += name_size + 3
    if reversed_:
        label = "CAPOVOLTA"
        lw = d.textlength(label, font=fh)
        d.rectangle((TEXT_X, y + 1, TEXT_X + lw + 7, y + 13), fill=0)
        d.text((TEXT_X + 4, y + 1), label, fill=1, font=fh)
        y += 16
    y += 4
    for ln in kw_lines:
        d.text((TEXT_X, y), ln, fill=0, font=fk)
        y += kw_size + 4
    return img


class TarocchiApp:
    name = "tarocchi"
    title = "Tarocchi"

    def __init__(self, cfg):
        self.cfg = cfg
        self.deck = load_deck()
        self.rng = secrets.SystemRandom()
        self.last = None
        if not os.path.isdir(CARDS_DIR):
            log.warning("immagini delle carte non trovate in %s", CARDS_DIR)

    def draw(self):
        while True:
            i = self.rng.randrange(len(self.deck))
            if i != self.last:
                break
        self.last = i
        rev = self.cfg.bool("TAROT_REVERSED") and self.rng.random() < 0.5
        return self.deck[i], rev

    def frame(self):
        card, rev = self.draw()
        log.info("carta: %s%s", card["name"], " (capovolta)" if rev else "")
        return draw_card(card, rev), self.cfg.float("TAROT_SECONDS")

    def close(self):
        pass
