"""Foto: mostra una foto caricata dal telefono, in bianco e nero.

La foto originale non viene mai scritta su disco: si elabora in memoria e si
salva solo la versione finale 1-bit 250x122 (pochi KB), che sostituisce
sempre la precedente.
"""
import io
import logging
import os

from PIL import Image, ImageEnhance, ImageOps

import config
import render

log = logging.getLogger("etere.foto")
W, H = render.W, render.H
FILE = "etere-foto.png"
FITS = {"riempi": "riempie lo schermo (taglia i bordi)", "intera": "foto intera (bande bianche)"}
MAX_UPLOAD = 30 * 1024 * 1024


class PhotoError(ValueError):
    pass


def process(data, fit="riempi", method="floyd"):
    """Byte di un'immagine (JPEG, PNG, ...) -> immagine 1-bit 250x122."""
    try:
        im = Image.open(io.BytesIO(data))
        im.draft("L", (W * 4, H * 4))  # i JPEG grandi vengono decodificati gia' ridotti
        im = ImageOps.exif_transpose(im)  # foto del telefono ruotate nel verso giusto
        im = im.convert("L")
    except Exception as e:
        raise PhotoError("formato non riconosciuto (prova a inviarla come JPEG)") from e
    if fit == "intera":
        im = ImageOps.pad(im, (W, H), Image.LANCZOS, color=255)
    else:
        im = ImageOps.fit(im, (W, H), Image.LANCZOS)
    im = ImageOps.autocontrast(im, cutoff=1)
    im = ImageEnhance.Sharpness(im).enhance(1.4)
    return render.dither(im, method)


def save(cfg, img):
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    path = cfg.data_path(FILE)
    config.write_file(path, buf.getvalue())  # sovrascrive la foto precedente
    log.info("foto salvata in %s (%d byte)", path, buf.tell())


class FotoApp:
    name = "foto"
    title = "Foto"

    def __init__(self, cfg):
        self.cfg = cfg

    def frame(self):
        path = self.cfg.data_path(FILE)
        if os.path.exists(path):
            img = Image.open(path).convert("1")
        else:
            img = render.message("nessuna foto\n\ncaricala dalla pagina\ndi controllo sul telefono")
        return img, 24 * 3600  # immagine ferma: si aggiorna solo con una nuova foto

    def close(self):
        pass
