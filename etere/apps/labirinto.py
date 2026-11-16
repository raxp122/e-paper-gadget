"""Labirinto: ne genera uno nuovo e lo fa esplorare a un "topolino".

Il topolino entra in alto a sinistra e cerca l'uscita in basso a destra.
A ogni bivio sceglie a caso; nei vicoli ciechi torna indietro. Lascia una
traccia: la linea e' il cammino attuale, i puntini sono i tratti gia'
esplorati e abbandonati. Trovata l'uscita, mostra il percorso per qualche
passo e genera un labirinto nuovo.
"""
import logging
import random
import secrets

from PIL import Image, ImageDraw

import render

log = logging.getLogger("etere.labirinto")
W, H = render.W, render.H
HOLD = 4
DIRS = ((0, 1), (1, 0), (0, -1), (-1, 0))  # destra, giu', sinistra, su


def generate(rows, cols, rng):
    """Labirinto 'perfetto' (un solo percorso tra due celle qualsiasi) con
    l'algoritmo del backtracking: corridoi lunghi e tortuosi.
    Ritorna l'insieme dei passaggi aperti {((r,c),(r2,c2)), ...}."""
    open_ = set()
    seen = {(0, 0)}
    stack = [(0, 0)]
    while stack:
        r, c = stack[-1]
        nb = [(r + dr, c + dc) for dr, dc in DIRS
              if 0 <= r + dr < rows and 0 <= c + dc < cols and (r + dr, c + dc) not in seen]
        if not nb:
            stack.pop()
            continue
        n = rng.choice(nb)
        open_.add(((r, c), n))
        open_.add((n, (r, c)))
        seen.add(n)
        stack.append(n)
    return open_


class LabirintoApp:
    name = "labirinto"
    title = "Labirinto"
    partial = True

    def __init__(self, cfg):
        self.cfg = cfg
        self.cell = max(4, int(cfg.str("MAZE_CELL")))
        self.cols = (W - 1) // self.cell
        self.rows = (H - 1) // self.cell
        self.ox = (W - (self.cols * self.cell + 1)) // 2
        self.oy = (H - (self.rows * self.cell + 1)) // 2
        self.new_maze()

    def new_maze(self):
        self.rng = random.Random(secrets.randbits(64))
        self.open = generate(self.rows, self.cols, self.rng)
        self.start, self.exit = (0, 0), (self.rows - 1, self.cols - 1)
        self.stack = [self.start]
        self.visited = {self.start}
        self.done = False
        self.ending = None
        self.reset_next = True
        self.base = self._walls()
        log.info("nuovo labirinto %dx%d", self.cols, self.rows)

    def _xy(self, r, c):
        return self.ox + c * self.cell, self.oy + r * self.cell

    def _center(self, rc):
        x, y = self._xy(*rc)
        return x + self.cell // 2, y + self.cell // 2

    def _walls(self):
        img = Image.new("1", (W, H), 1)
        d = ImageDraw.Draw(img)
        s = self.cell
        for r in range(self.rows):
            for c in range(self.cols):
                x, y = self._xy(r, c)
                if r == 0:
                    d.line((x, y, x + s, y), fill=0)
                if c == 0 and (r, c) != self.start:          # ingresso aperto a sinistra
                    d.line((x, y, x, y + s), fill=0)
                if ((r, c), (r, c + 1)) not in self.open and (r, c) != self.exit:
                    d.line((x + s, y, x + s, y + s), fill=0)  # muro a destra (uscita aperta)
                if ((r, c), (r + 1, c)) not in self.open:
                    d.line((x, y + s, x + s, y + s), fill=0)  # muro in basso
        return img

    def _advance(self):
        """Un passo del topolino: avanza in una cella nuova o torna indietro."""
        here = self.stack[-1]
        if here == self.exit:
            self.done = True
            return
        r, c = here
        nb = [(r + dr, c + dc) for dr, dc in DIRS
              if ((r, c), (r + dr, c + dc)) in self.open and (r + dr, c + dc) not in self.visited]
        if nb:
            n = self.rng.choice(nb)
            self.visited.add(n)
            self.stack.append(n)
        else:
            self.stack.pop()

    def draw(self):
        img = self.base.copy()
        d = ImageDraw.Draw(img)
        on_path = set(self.stack)
        for rc in self.visited - on_path:       # tratti esplorati e abbandonati
            x, y = self._center(rc)
            d.point((x, y), fill=0)
        pts = [self._center(rc) for rc in self.stack]
        if len(pts) > 1:
            d.line(pts, fill=0, width=2)
        x, y = pts[-1]                          # il topolino
        d.rectangle((x - 2, y - 2, x + 2, y + 2), fill=0)
        return img

    def frame(self):
        if self.ending is not None and self.ending <= 0:
            self.new_maze()
        if self.ending is None:
            for _ in range(max(1, int(self.cfg.str("MAZE_STEPS")))):
                self._advance()
                if self.done:
                    self.ending = HOLD
                    log.info("uscita trovata: percorso di %d celle, %d esplorate",
                             len(self.stack), len(self.visited))
                    break
        else:
            self.ending -= 1
        return self.draw(), self.cfg.float("MAZE_SECONDS")

    def close(self):
        pass
