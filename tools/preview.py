#!/usr/bin/env python3
"""Anteprima sul PC di come vengono gli scatti delle varie sorgenti, con dati
radio simulati che passano dallo STESSO codice usato sul Pi.

    python3 tools/preview.py anteprima.png
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "etere"))
import config  # noqa: E402
import render  # noqa: E402
import sources  # noqa: E402


class FakeRssi(sources.RssiSource):
    """Trasmettitori con un livello tipico, beacon ~10/s, fading e,
    a volte, una persona che si muove (il segnale 'trema' e si allarga)."""

    def __init__(self, seed):
        super().__init__(config.Config(path=os.devnull))
        self.rng = np.random.default_rng(seed)

    def _listen(self, seconds):
        rng = self.rng
        t, v = [], []
        n_tx = rng.integers(4, 12)
        levels = rng.uniform(-90, -35, n_tx)
        rates = rng.choice([10, 10, 10, 30, 80], n_tx)
        move = rng.random() < 0.8
        m0 = rng.uniform(0.1, 0.6) * seconds
        m1 = m0 + rng.uniform(0.2, 0.35) * seconds
        drift = rng.uniform(-3, 3, n_tx)
        for lvl, rate, dr in zip(levels, rates, drift):
            tt = np.sort(rng.uniform(0, seconds, int(rate * seconds)))
            slow = 2.0 * np.sin(2 * np.pi * tt / rng.uniform(3, 9) + rng.uniform(0, 6))
            jitter = rng.normal(0, 1.2, len(tt))
            moving = (tt > m0) & (tt < m1) if move else np.zeros(len(tt), bool)
            jitter[moving] += rng.normal(0, 6, moving.sum())
            t += list(tt)
            v += list(np.round(lvl + dr * tt / seconds + slow + jitter))
        return t, v

    def capture(self, seconds):
        t, v = self._listen(seconds)
        nb = self.DBM_MAX - self.DBM_MIN + 1
        rows = np.zeros((len(v), nb))
        b = np.clip(np.asarray(v) - self.DBM_MIN, 0, nb - 1).astype(int)
        rows[np.arange(len(v)), b] = 1.0
        counts = sources.bin_columns(t, rows, 0, seconds) * len(v) / sources.COLS
        return np.log1p(counts[::-1] * 50)


def fake_scan(seed, n_scans=48):
    rng = np.random.default_rng(seed)
    n_ap = rng.integers(5, 18)
    aps = [(2412 + 5 * rng.integers(0, 12), rng.uniform(-90, -40)) for _ in range(n_ap)]
    cols = []
    for _ in range(n_scans):
        seen = [(f, s + rng.normal(0, 2.5)) for f, s in aps if rng.random() < 0.85]
        cols.append(sources.spectrum_column(seen))
    return np.array(cols).T


def main(path):
    seeds = [1, 2, 3, 4, 5]
    rows = [
        ("rssi - 1 canale (modalita' monitor)",
         [render.render(FakeRssi(s).capture(10), 0.6, FakeRssi.blur) for s in seeds]),
        ("scan - ripiego (dopo ~48 scansioni)",
         [render.render(sources.smooth_scans(fake_scan(s)), 0.0, sources.ScanSource.blur) for s in seeds]),
        ("csi - se un giorno sara' disponibile (simulato)",
         [render.render(sources.SimSource(seed=s).capture(0), 0.6) for s in seeds]),
    ]
    sc, gap, lab = 2, 10, 24
    cw, ch = 250 * sc, 122 * sc
    sheet = Image.new("L", (gap + len(seeds) * (cw + gap), len(rows) * (ch + lab + gap)), 255)
    d = ImageDraw.Draw(sheet)
    y = 0
    for title, imgs in rows:
        d.text((gap, y + 6), title, fill=0, font=render._font(15))
        for j, im in enumerate(imgs):
            sheet.paste(im.convert("L").resize((cw, ch), Image.NEAREST), (gap + j * (cw + gap), y + lab))
        y += ch + lab + gap
    sheet.save(path)
    print("salvato", path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "anteprima.png")
