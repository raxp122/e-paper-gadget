"""Uscita: pannello Waveshare 2.13" oppure file PNG (per lo sviluppo sul PC)."""
import importlib
import inspect
import logging
import os
import sys

log = logging.getLogger("etere.display")
HERE = os.path.dirname(os.path.abspath(__file__))


class EpdDisplay:
    def __init__(self, model):
        sys.path.insert(0, os.path.join(HERE, "lib"))
        mod = importlib.import_module(f"waveshare_epd.epd2in13_{model}")
        self.epd = mod.EPD()
        self.model = model

    def show(self, img):
        e = self.epd
        # refresh COMPLETO ogni volta: immagine pulita e senza aloni
        if inspect.signature(e.init).parameters:
            e.init(e.FULL_UPDATE)
        else:
            e.init()
        e.display(e.getbuffer(img))
        # deep sleep + alimentazione del pannello spenta: da qui in poi
        # l'immagine e' "ferma" e si puo' staccare la corrente
        e.sleep()


class FileDisplay:
    def __init__(self, path, scale=3):
        self.path = path
        self.scale = scale
        self.n = 0

    def show(self, img):
        self.n += 1
        big = img.convert("L").resize((img.width * self.scale, img.height * self.scale), 0)
        big.save(self.path)
        log.info("scatto %d salvato in %s", self.n, self.path)


def make(cfg, out=None):
    if out:
        return FileDisplay(out)
    return EpdDisplay(cfg.str("EPD").upper())
