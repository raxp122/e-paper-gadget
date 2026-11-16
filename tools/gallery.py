#!/usr/bin/env python3
"""Genera le immagini del README (docs/img/) con lo stesso codice del Pi.

    python3 tools/gallery.py

Per i tarocchi servono le scansioni in etere/data/tarocchi/cards (le scarica
install.sh); senza, la carta compare come segnaposto.
"""
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "etere"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import config  # noqa: E402
import render  # noqa: E402
import sources  # noqa: E402
from apps.labirinto import LabirintoApp  # noqa: E402
from apps.mandelbrot import MandelbrotApp  # noqa: E402
from apps.tarocchi import draw_card, load_deck  # noqa: E402
from apps.vita import VitaApp  # noqa: E402
from preview import fake_scan  # noqa: E402

OUT = os.path.join(ROOT, "docs", "img")
SCALE = 3


def frame(img):
    """Ingrandisce e aggiunge una cornice, come il bordo del pannello."""
    big = img.convert("L").resize((img.width * SCALE, img.height * SCALE), Image.NEAREST)
    pad = 10
    out = Image.new("L", (big.width + 2 * pad, big.height + 2 * pad), 225)
    out.paste(big, (pad, pad))
    ImageDraw.Draw(out).rectangle((pad - 1, pad - 1, pad + big.width, pad + big.height), outline=60)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = config.Config(path=os.devnull)
    shots = {}

    m = MandelbrotApp(cfg)
    for _ in range(9):
        img, _ = m.frame()
    shots["mandelbrot"] = img

    deck = {c["img"]: c for c in load_deck()}
    shots["tarocchi"] = draw_card(deck["m17"], False)
    shots["tarocchi-capovolta"] = draw_card(deck["c13"], True)

    v = VitaApp(cfg)
    for _ in range(40):
        img, _ = v.frame()
    shots["vita"] = img

    lab = LabirintoApp(cfg)
    for _ in range(14):
        img, _ = lab.frame()
    shots["labirinto"] = img

    m = sources.smooth_scans(fake_scan(7))
    shots["etere"] = render.render(m, 0.0, sources.ScanSource.blur, view="intensita", method="bayer")

    for name, img in shots.items():
        path = os.path.join(OUT, name + ".png")
        frame(img).save(path, optimize=True)
        print("salvato", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
