#!/usr/bin/env python3
"""Etere: un gadget e-paper con piu' app (frattale, tarocchi, onde Wi-Fi).

All'accensione parte l'app scelta come predefinita. Dal telefono, collegato
alla rete del gadget, si apre una paginetta per cambiare app e impostazioni.
Le app lente fanno un refresh completo e mettono il pannello a dormire, quelle
veloci (vita, labirinto) usano il refresh parziale. Si puo' staccare la
corrente quando si vuole, tranne durante un aggiornamento.
"""
import argparse
import logging
import sys
import time

import apps
import config
import display
import render
import rete
import sources
import web

log = logging.getLogger("etere")


def args_parser():
    p = argparse.ArgumentParser(description="Etere - gadget e-paper")
    p.add_argument("--app", help="app da avviare: " + " | ".join(apps.APPS))
    p.add_argument("--source", help="(app etere) auto | csi | rssi | scan | sim")
    p.add_argument("--out", help="salva in PNG invece di usare il display")
    p.add_argument("--once", action="store_true", help="un solo frame e poi esce")
    p.add_argument("--web-port", type=int, help="porta della pagina di controllo (0 = spenta)")
    p.add_argument("--probe", action="store_true", help="prova le sorgenti radio")
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


def run(cfg, out, ctl, once=False):
    rot = 180 if cfg.str("ROTATE").strip() == "180" else 0
    while True:
        name = ctl.current
        try:
            app = apps.create(name, cfg)
        except Exception as e:  # nome sbagliato o app rotta: non lasciamo lo schermo vuoto
            log.exception("app %s non avviata", name)
            out.show(render.message(f"app '{name}'\nnon disponibile\n\n{type(e).__name__}", rot))
            if name == "mandelbrot":
                return 1
            ctl.current = "mandelbrot"
            continue
        log.info("app: %s", name)
        ctl.changed.clear()
        try:
            while not ctl.changed.is_set():
                t0 = time.monotonic()
                img, interval = app.frame()
                if ctl.changed.is_set():
                    break                       # nel frattempo e' stata scelta un'altra app
                # app veloci: refresh parziale; le altre: completo + sleep del pannello
                out.show(img.rotate(rot) if rot else img,
                         partial=getattr(app, "partial", False),
                         reset=getattr(app, "reset_next", False))
                app.reset_next = False
                if once:
                    return 0
                wait = interval - (time.monotonic() - t0)
                ctl.changed.wait(max(wait, 0))
        finally:
            app.close()


def main(argv=None):
    a = args_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(name)s: %(message)s")
    overrides = {}
    if a.source:
        overrides["SOURCE"] = a.source
    cfg = config.Config(overrides, path=a.config)

    if a.probe:
        return probe(cfg)

    if a.test_display:
        display.make(cfg, a.out).show(render.test_pattern())
        return 0

    if not a.out and config.find_boot_file("etere-off"):
        log.info("trovato etere-off sulla partizione di boot: modalita' manutenzione, esco")
        return 0

    start_app = a.app or ("etere" if a.source else cfg.str("APP").strip().lower())
    if start_app not in apps.APPS:
        log.error("app sconosciuta '%s', uso mandelbrot", start_app)
        start_app = "mandelbrot"
    ctl = web.Controller(cfg, start_app)
    port = a.web_port if a.web_port is not None else (0 if a.out else int(cfg.str("WEB_PORT")))
    if port:
        web.start(ctl, port)
    if not a.out:
        rete.start_fallback(cfg)   # senza rete conosciuta, accende "raspberry"
    return run(cfg, display.make(cfg, a.out), ctl, a.once)


if __name__ == "__main__":
    sys.exit(main())
