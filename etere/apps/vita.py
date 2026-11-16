"""Gioco della vita di Conway su un mondo che si richiude su se stesso (toro).

Ogni N secondi calcola una generazione. Quando il mondo si stabilizza (tutto
fermo, oppure figure che si ripetono uguali) mostra ancora qualche passo e
riparte da una nuova disposizione casuale.
"""
import collections
import logging
import secrets

import numpy as np
from PIL import Image, ImageDraw

import render

log = logging.getLogger("etere.vita")
W, H = render.W, render.H
HOLD = 4  # frame mostrati dopo la stabilizzazione, prima di ripartire


def step(grid):
    """Una generazione: nasce con 3 vicini, sopravvive con 2 o 3."""
    n = sum(np.roll(np.roll(grid, dy, 0), dx, 1)
            for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0))
    return ((n == 3) | (grid & (n == 2))).astype(np.uint8)


class VitaApp:
    name = "vita"
    title = "Gioco della vita"
    partial = True

    def __init__(self, cfg):
        self.cfg = cfg
        self.cell = max(2, int(cfg.str("LIFE_CELL")))
        self.rows, self.cols = H // self.cell, W // self.cell
        self.reset_next = True
        self.new_world()

    def new_world(self):
        rng = np.random.default_rng(secrets.randbits(64))
        density = min(0.9, max(0.05, self.cfg.float("LIFE_DENSITY")))
        self.grid = (rng.random((self.rows, self.cols)) < density).astype(np.uint8)
        self.gen = 0
        self.seen = collections.deque(maxlen=64)   # per riconoscere i cicli
        self.ending = None
        self.reset_next = True                     # nuovo mondo: refresh completo
        log.info("nuovo mondo %dx%d, %d celle vive", self.cols, self.rows, int(self.grid.sum()))

    def draw(self):
        c = self.cell
        big = np.kron(self.grid, np.ones((c, c), np.uint8))
        img = Image.new("1", (W, H), 1)
        cells = Image.fromarray(((1 - big) * 255).astype("uint8"), "L").convert("1")
        img.paste(cells, ((W - big.shape[1]) // 2, (H - big.shape[0]) // 2))
        if self.cfg.bool("LIFE_LABEL"):
            txt = f"gen {self.gen}" + (" · stabile" if self.ending is not None else "")
            d = ImageDraw.Draw(img)
            f = render._font(10)
            w = int(d.textlength(txt, font=f)) + 6
            d.rectangle((W - w, H - 13, W - 1, H - 1), fill=1)
            d.text((W - w + 3, H - 13), txt, fill=0, font=f)
        return img

    def frame(self):
        if self.ending is not None and self.ending <= 0:
            self.new_world()
        img = self.draw()
        nxt = step(self.grid)
        if self.ending is None:
            key = nxt.tobytes()
            if (key in self.seen or not nxt.any()
                    or self.gen + 1 >= int(self.cfg.str("LIFE_MAX_GEN"))):
                self.ending = HOLD
                log.info("stabile alla generazione %d", self.gen + 1)
            self.seen.append(key)
        else:
            self.ending -= 1
        self.grid = nxt
        self.gen += 1
        return img, self.cfg.float("LIFE_SECONDS")

    def close(self):
        pass
