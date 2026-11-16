"""Uscita: pannello Waveshare 2.13" oppure file PNG (per lo sviluppo sul PC).

Due modi di aggiornare il pannello:
- completo (show con partial=False): refresh pulito, poi il pannello va in
  deep sleep. Per le app lente (frattale, tarocchi, foto).
- parziale (partial=True): ~0.3 s, senza lampeggio, per le app veloci (vita,
  labirinto). Il primo frame e uno ogni FULL_EVERY sono completi, per
  cancellare gli aloni; tra un frame e l'altro il pannello resta pronto.
"""
import importlib
import inspect
import logging
import os
import sys

log = logging.getLogger("etere.display")
HERE = os.path.dirname(os.path.abspath(__file__))


class EpdDisplay:
    def __init__(self, model, full_every=30):
        sys.path.insert(0, os.path.join(HERE, "lib"))
        mod = importlib.import_module(f"waveshare_epd.epd2in13_{model}")
        self.epd = mod.EPD()
        self.model = model
        self.full_every = max(1, full_every)
        self.awake = False      # pannello inizializzato per i parziali
        self.partials = 0
        self.can_partial = hasattr(self.epd, "displayPartial") and hasattr(self.epd, "displayPartBaseImage")

    def _init_full(self):
        e = self.epd
        if inspect.signature(e.init).parameters:   # V2: init(update)
            e.init(e.FULL_UPDATE)
        else:
            e.init()

    def show(self, img, partial=False, reset=False):
        e = self.epd
        if partial and self.can_partial and self.model != "V2":
            buf = e.getbuffer(img)
            if not self.awake or reset or self.partials >= self.full_every:
                # refresh completo che fa da base per i parziali successivi
                self._init_full()
                e.displayPartBaseImage(buf)
                self.awake = True
                self.partials = 0
            else:
                e.displayPartial(buf)
                self.partials += 1
            return
        # refresh COMPLETO: immagine pulita e senza aloni
        self._init_full()
        e.display(e.getbuffer(img))
        # deep sleep + alimentazione del pannello spenta: da qui in poi
        # l'immagine e' "ferma" e si puo' staccare la corrente
        e.sleep()
        self.awake = False


class FileDisplay:
    def __init__(self, path, scale=3):
        self.path = path
        self.scale = scale
        self.n = 0

    def show(self, img, partial=False, reset=False):
        self.n += 1
        big = img.convert("L").resize((img.width * self.scale, img.height * self.scale), 0)
        big.save(self.path)
        log.debug("frame %d salvato in %s", self.n, self.path)


def make(cfg, out=None):
    if out:
        return FileDisplay(out)
    return EpdDisplay(cfg.str("EPD").upper(), int(cfg.str("EPD_FULL_EVERY")))
