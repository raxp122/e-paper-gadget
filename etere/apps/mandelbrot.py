"""Viaggio nel frattale: ogni frame scende piu' in profondita' nell'insieme
di Mandelbrot. Un "pilota automatico" sceglie a ogni passo un punto sul
bordo del frattale, cosi' il viaggio non finisce mai nel nero pieno o nel
vuoto. Ogni accensione e' un viaggio nuovo (punti scelti dal generatore
casuale del sistema). Nulla viene salvato.
"""
import logging
import math
import secrets

import numpy as np
from PIL import Image, ImageDraw

import render

log = logging.getLogger("etere.mandelbrot")
W, H = render.W, render.H
_rng = secrets.SystemRandom()

START_CENTER = complex(-0.6, 0.0)
START_HALF_WIDTH = 1.6        # meta' larghezza della vista iniziale
ZOOM = 0.55                   # a ogni passo la vista si restringe cosi'
MIN_HALF_WIDTH = 2e-12        # oltre, la precisione dei float64 finisce
STYLES = ("china", "incisione", "chiaroscuro")


def compute(center, half_width, max_iter):
    """Ritorna (nu, interno, dist): iterazione 'smussata', maschera dei punti
    che non scappano e stima della distanza dal bordo (in unita' del piano)."""
    hh = half_width * H / W
    xs = np.linspace(center.real - half_width, center.real + half_width, W)
    ys = np.linspace(center.imag + hh, center.imag - hh, H)
    c = (xs[None, :] + 1j * ys[:, None]).ravel()
    n = c.size
    z = np.zeros(n, complex)
    dz = np.zeros(n, complex)
    nu = np.zeros(n)
    dist = np.zeros(n)
    inside = np.ones(n, bool)
    idx = np.arange(n)
    zc, dzc, cc = z, dz, c
    bail = 256.0
    for it in range(max_iter):
        dzc = 2.0 * zc * dzc + 1.0
        zc = zc * zc + cc
        a2 = zc.real * zc.real + zc.imag * zc.imag
        out = a2 > bail * bail
        if out.any():
            o = idx[out]
            az = np.sqrt(a2[out])
            inside[o] = False
            nu[o] = it + 1 - np.log2(np.log(az))
            dist[o] = az * np.log(az) / np.maximum(np.abs(dzc[out]), 1e-300)
            keep = ~out
            idx, zc, dzc, cc = idx[keep], zc[keep], dzc[keep], cc[keep]
            if idx.size == 0:
                break
    shape = (H, W)
    return nu.reshape(shape), inside.reshape(shape), dist.reshape(shape)


def stylize(nu, inside, dist, half_width, style):
    px = 2 * half_width / W                     # dimensione di un pixel
    if style == "china":
        # disegno a china: il bordo come linea nera, interno nero, fuori bianco
        # con un velo di grigio vicino al bordo
        d = dist / px
        g = np.clip(np.log1p(d) / np.log1p(40), 0, 1) ** 0.6
        g[inside] = 0.0
        return g
    esc = ~inside
    if style == "incisione":
        # bande sottili come le linee di un'incisione
        g = np.zeros_like(nu)
        if esc.any():
            g[esc] = 0.5 + 0.5 * np.cos(np.sqrt(nu[esc]) * 3.0)
        edge = (dist / px) < 0.7
        g[edge & esc] = 0.0
        g[inside] = 0.0
        return g
    if style == "chiaroscuro":
        # grigi equalizzati: la classica resa morbida
        g = np.zeros_like(nu)
        if esc.any():
            v = nu[esc]
            ranks = np.argsort(np.argsort(v))
            g[esc] = 1.0 - ranks / max(len(v) - 1, 1)
        g[inside] = 0.0
        return g
    raise ValueError(f"stile sconosciuto: {style} (usa {', '.join(STYLES)})")


class Journey:
    def __init__(self, style="china"):
        self.style = style
        self.reset()

    def reset(self):
        self.center = START_CENTER
        self.half_width = START_HALF_WIDTH
        self.step = 0

    def max_iter(self):
        depth = math.log10(START_HALF_WIDTH / self.half_width)
        return int(min(900, 120 + 70 * depth))

    def _next_target(self, nu, inside, dist):
        """Sceglie il prossimo centro: un punto vicino al bordo, non troppo
        lontano dal centro della vista attuale."""
        px = 2 * self.half_width / W
        near_edge = (~inside) & (dist / px < 2.0)
        yy, xx = np.mgrid[0:H, 0:W]
        central = (np.abs(xx - W / 2) < W * 0.3) & (np.abs(yy - H / 2) < H * 0.3)
        cand = np.argwhere(near_edge & central)
        if len(cand) == 0:
            cand = np.argwhere(near_edge)
        if len(cand) == 0:
            return None
        y, x = cand[_rng.randrange(len(cand))]
        hh = self.half_width * H / W
        re = self.center.real - self.half_width + 2 * self.half_width * x / (W - 1)
        im = self.center.imag + hh - 2 * hh * y / (H - 1)
        return complex(re, im)

    def frame(self):
        nu, inside, dist = compute(self.center, self.half_width, self.max_iter())
        img = stylize(nu, inside, dist, self.half_width, self.style)
        target = self._next_target(nu, inside, dist)
        depth = START_HALF_WIDTH / self.half_width
        log.info("passo %d, ingrandimento %.3g x", self.step, depth)
        if target is None or self.half_width * ZOOM < MIN_HALF_WIDTH:
            log.info("fine del viaggio, ne comincio uno nuovo")
            self.reset()
        else:
            self.center = target
            self.half_width *= ZOOM
            self.step += 1
        return img, depth


def caption(img1bit, depth):
    """Piccola etichetta con l'ingrandimento nell'angolo in basso a destra."""
    if depth < 2:
        return img1bit
    txt = f"x{depth:.0e}".replace("e+0", "e").replace("e+", "e") if depth >= 1e4 else f"x{depth:.0f}"
    d = ImageDraw.Draw(img1bit)
    f = render._font(10)
    w = int(d.textlength(txt, font=f)) + 6
    d.rectangle((W - w, H - 13, W - 1, H - 1), fill=1)
    d.text((W - w + 3, H - 13), txt, fill=0, font=f)
    return img1bit


class MandelbrotApp:
    name = "mandelbrot"
    title = "Viaggio nel frattale"

    def __init__(self, cfg):
        self.cfg = cfg
        self.journey = Journey(cfg.str("MANDEL_STYLE").strip().lower())

    def frame(self):
        g, depth = self.journey.frame()
        im = Image.fromarray((np.clip(g, 0, 1) * 255).astype("uint8"), "L")
        img = render.dither(im, "floyd")
        if self.cfg.bool("MANDEL_ZOOM_LABEL"):
            img = caption(img, depth)
        return img, self.cfg.float("MANDEL_SECONDS")

    def close(self):
        pass
