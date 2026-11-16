#!/usr/bin/env python3
"""Etere: una Polaroid dell'etere radio su e-paper.

Ciclo: accensione -> ascolto (esposizione) -> immagine -> refresh completo
-> lo schermo resta fermo mentre si ascolta per lo scatto successivo.
Niente viene salvato: lo scatto esiste solo sul display.
"""
import argparse
import logging
import os
import sys
import time

import numpy as np

import config
import display
import render
import sources

log = logging.getLogger("etere")
NO_SOURCE = 3  # il servizio systemd non riparte in loop con questo codice


def wait_for_iface(name, timeout=40):
    """Al boot il Wi-Fi puo' comparire qualche secondo dopo di noi."""
    end = time.monotonic() + timeout
    while not os.path.exists(f"/sys/class/net/{name}") and time.monotonic() < end:
        time.sleep(1)


def args_parser():
    p = argparse.ArgumentParser(description="Etere - Polaroid radio")
    p.add_argument("--source", help="auto | csi | rssi | scan | sim")
    p.add_argument("--out", help="salva in PNG invece di usare il display")
    p.add_argument("--once", action="store_true", help="un solo scatto e poi esce")
    p.add_argument("--probe", action="store_true", help="prova le sorgenti e dice quali funzionano")
    p.add_argument("--test-display", action="store_true", help="disegna una schermata di prova")
    p.add_argument("--config", help="file di configurazione alternativo")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def probe(cfg):
    cfg.values["KEEP_WIFI"] = "1"  # non tagliamo il ramo su cui siamo seduti (SSH)
    ok = []
    for name in ("csi", "rssi", "scan"):
        src = sources.SOURCES[name](cfg)
        try:
            src.setup()
            res = src.probe()
        except (sources.SourceError, OSError) as e:
            res = False
            print(f"  {name:5s} NO   ({e})")
        else:
            print(f"  {name:5s} {'SI' if res else 'NO   (nessun segnale)'}")
        finally:
            try:
                src.close()
            except Exception:
                pass
        if res:
            ok.append(name)
    print("Funzionano:", ", ".join(ok) or "nessuna")
    return 0 if ok else 1


def main(argv=None):
    a = args_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(name)s: %(message)s")
    overrides = {"SOURCE": a.source} if a.source else None
    cfg = config.Config(overrides, path=a.config)
    rot = 180 if cfg.str("ROTATE").strip() == "180" else 0

    if a.probe:
        return probe(cfg)

    if a.test_display:
        display.make(cfg, a.out).show(render.test_pattern(rot))
        return 0

    if not a.out and config.find_boot_file("etere-off"):
        log.info("trovato etere-off sulla partizione di boot: modalita' manutenzione, esco")
        return 0

    out = display.make(cfg, a.out)
    if cfg.str("SOURCE").lower() != "sim":
        wait_for_iface(cfg.str("IFACE"))
    try:
        src = sources.choose(cfg)
    except sources.SourceError as e:
        log.error("nessuna sorgente: %s", e)
        out.show(render.message("etere\n\nnessuna radio in ascolto", rot))
        return NO_SOURCE

    clean = cfg.float("CLEAN")
    invert = cfg.bool("INVERT")
    view = cfg.str("VIEW").strip().lower()
    method = cfg.str("DITHER").strip().lower()
    try:  # nome sbagliato in etere.conf: lo dico sullo schermo invece di crashare
        render.apply_view(np.zeros((2, 2)), view)
        render.dither(render.message(""), method)
    except ValueError as e:
        log.error("%s", e)
        out.show(render.message(f"etere.conf:\nVIEW={view}  DITHER={method}\nvalore non valido", rot))
        return NO_SOURCE
    exposure = cfg.float("FIRST_EXPOSURE_SECONDS")
    while True:
        t = time.monotonic()
        matrix = src.capture(exposure)          # lo schermo intanto e' fermo
        img = render.render(matrix, clean * src.clean_factor, src.blur, invert, rot, view, method)
        out.show(img)                           # refresh completo + sleep del pannello
        log.info("scatto (%s) in %.1fs", src.name, time.monotonic() - t)
        if a.once:
            break
        exposure = cfg.float("EXPOSURE_SECONDS")
    src.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
