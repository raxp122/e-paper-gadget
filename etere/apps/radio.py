"""Etere: la Polaroid delle onde radio (il primo progetto), come app."""
import logging
import os
import time

import render
import sources

log = logging.getLogger("etere.radio")


def wait_for_iface(name, timeout=40):
    """Al boot il Wi-Fi puo' comparire qualche secondo dopo di noi."""
    end = time.monotonic() + timeout
    while not os.path.exists(f"/sys/class/net/{name}") and time.monotonic() < end:
        time.sleep(1)


class RadioApp:
    name = "etere"
    title = "Etere (onde Wi-Fi)"

    def __init__(self, cfg):
        self.cfg = cfg
        self.src = None
        self.first = True
        self.rot = 180 if cfg.str("ROTATE").strip() == "180" else 0

    def frame(self):
        cfg = self.cfg
        if self.src is None:
            if cfg.str("SOURCE").lower() != "sim":
                wait_for_iface(cfg.str("IFACE"))
            try:
                self.src = sources.choose(cfg)
            except sources.SourceError as e:
                log.error("nessuna sorgente radio: %s", e)
                return render.message("etere\n\nla radio non e' disponibile\n"
                                      "(con la rete del gadget attiva\nnon si puo' ascoltare)"), 60
        exposure = cfg.float("FIRST_EXPOSURE_SECONDS" if self.first else "EXPOSURE_SECONDS")
        self.first = False
        m = self.src.capture(exposure)  # lo schermo intanto resta fermo
        view = cfg.str("VIEW").strip().lower()
        method = cfg.str("DITHER").strip().lower()
        try:
            img = render.render(m, cfg.float("CLEAN") * self.src.clean_factor, self.src.blur,
                                cfg.bool("INVERT"), 0, view, method)
        except ValueError as e:
            return render.message(f"etere.conf:\n{e}"), 60
        return img, 0  # l'attesa e' gia' l'esposizione del prossimo scatto

    def close(self):
        if self.src:
            self.src.close()
            self.src = None

