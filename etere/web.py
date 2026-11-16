"""Paginetta di controllo per il telefono.

Il gadget crea la rete Wi-Fi "raspberry". Il suo DNS risponde con l'indirizzo
del Pi a qualunque nome, quindi il telefono crede che serva un "accesso" e
apre da solo questa pagina. Funziona anche scrivendo http://10.42.0.1
nel browser. Nessun JavaScript: i mini-browser dei captive portal sono
molto limitati.
"""
import html
import logging
import threading
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import apps
from apps import foto
from apps.mandelbrot import STYLES

log = logging.getLogger("etere.web")

DESCR = {
    "mandelbrot": "Scende sempre più in profondità nel frattale. Ogni accensione è un viaggio nuovo.",
    "tarocchi": "Una carta a caso dal mazzo completo di 78, dritta o capovolta.",
    "vita": "Il gioco della vita di Conway: una generazione ogni pochi secondi, finché il mondo si stabilizza. Poi riparte.",
    "labirinto": "Genera un labirinto e un topolino lo esplora fino all'uscita. Poi ne genera un altro.",
    "foto": "L'ultima foto caricata qui sotto, in bianco e nero.",
    "etere": "Il ritratto delle reti Wi-Fi intorno. Non funziona mentre il gadget crea la sua rete.",
}

CSS = """
:root{--bg:#f4f1ea;--fg:#1c1b19;--mute:#6b675f;--card:#fffdf8;--line:#d9d3c6;--acc:#1c1b19;--accfg:#f4f1ea}
@media (prefers-color-scheme:dark){:root{--bg:#161513;--fg:#ece8df;--mute:#a19c91;--card:#211f1c;--line:#3a3732;--acc:#ece8df;--accfg:#161513}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:520px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:26px;margin:4px 0 2px;letter-spacing:.5px}h2{font-size:15px;text-transform:uppercase;
letter-spacing:1px;color:var(--mute);margin:28px 0 10px}
.now{color:var(--mute);margin:0 0 6px}.ok{background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:10px 12px;margin:12px 0}
.app{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin:10px 0}
.app.on{border-color:var(--fg)}.app h3{margin:0 0 4px;font-size:18px}.app p{margin:0 0 12px;color:var(--mute);font-size:14px}
.tag{display:inline-block;font-size:12px;border:1px solid var(--fg);border-radius:99px;padding:1px 8px;margin-left:6px;vertical-align:2px}
.row{display:flex;gap:8px;flex-wrap:wrap}form{margin:0}
button{font:inherit;font-size:15px;padding:10px 14px;border-radius:10px;border:1px solid var(--fg);
background:transparent;color:var(--fg);min-height:44px}button.pri{background:var(--acc);color:var(--accfg)}
fieldset{border:1px solid var(--line);border-radius:12px;background:var(--card);padding:12px 14px;margin:10px 0}
legend{padding:0 6px;font-weight:600}label{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:8px 0}
input[type=file]{font:inherit;font-size:14px;max-width:100%;padding:8px 0}
input[type=number],select{font:inherit;padding:8px;border-radius:8px;border:1px solid var(--line);
background:var(--bg);color:var(--fg);width:110px}input[type=checkbox]{width:22px;height:22px}
footer{color:var(--mute);font-size:13px;margin-top:28px}
"""


def page(ctl, msg=""):
    cfg = ctl.cfg
    e = html.escape
    out = ["<!doctype html><html lang='it'><head><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width,initial-scale=1'>",
           f"<title>Etere</title><style>{CSS}</style></head><body><main>",
           "<h1>Etere</h1>",
           f"<p class='now'>Ora sullo schermo: <b>{e(apps.APPS[ctl.current].title)}</b></p>"]
    if msg:
        out.append(f"<div class='ok'>{e(msg)}</div>")
    out.append("<h2>App</h2>")
    default = cfg.str("APP")
    for name, cls in apps.APPS.items():
        on = " on" if name == ctl.current else ""
        tag = "<span class='tag'>all'avvio</span>" if name == default else ""
        out.append(f"<div class='app{on}'><h3>{e(cls.title)}{tag}</h3><p>{e(DESCR.get(name, ''))}</p>"
                   "<div class='row'>"
                   f"<form method='post' action='/mostra'><input type='hidden' name='app' value='{e(name)}'>"
                   "<button class='pri'>Mostra adesso</button></form>")
        if name != default:
            out.append(f"<form method='post' action='/predefinita'><input type='hidden' name='app' value='{e(name)}'>"
                       "<button>Usa all'avvio</button></form>")
        out.append("</div></div>")
    fits = "".join(f"<option value='{k}'>{e(v)}</option>" for k, v in foto.FITS.items())
    out.append(
        "<h2>Carica una foto</h2>"
        "<form method='post' action='/foto' enctype='multipart/form-data'><fieldset>"
        "<legend>Foto</legend>"
        "<input type='file' name='foto' accept='image/*' required>"
        f"<label>Inquadratura<select name='fit'>{fits}</select></label>"
        "<label>Puntinato<select name='dither'><option value='floyd'>morbido</option>"
        "<option value='bayer'>a reticolo</option></select></label>"
        "<p style='color:var(--mute);font-size:13px;margin:6px 0 0'>Diventa in bianco e nero e "
        "sostituisce la foto precedente. L'originale non viene salvato.</p>"
        "</fieldset><button class='pri'>Carica e mostra</button></form>")
    chk = lambda k: " checked" if cfg.bool(k) else ""  # noqa: E731
    opts = "".join(f"<option{' selected' if s == cfg.str('MANDEL_STYLE') else ''}>{s}</option>" for s in STYLES)
    out.append(
        "<h2>Impostazioni</h2><form method='post' action='/impostazioni'>"
        "<fieldset><legend>Viaggio nel frattale</legend>"
        f"<label>Nuovo passo ogni (secondi, o appena pronto se ci mette di più)<input type='number' name='MANDEL_SECONDS' min='15' max='3600' value='{e(cfg.str('MANDEL_SECONDS'))}'></label>"
        f"<label>Stile<select name='MANDEL_STYLE'>{opts}</select></label>"
        f"<label>Mostra l'ingrandimento<input type='checkbox' name='MANDEL_ZOOM_LABEL' value='1'{chk('MANDEL_ZOOM_LABEL')}></label>"
        "</fieldset><fieldset><legend>Tarocchi</legend>"
        f"<label>Nuova carta ogni (secondi)<input type='number' name='TAROT_SECONDS' min='15' max='3600' value='{e(cfg.str('TAROT_SECONDS'))}'></label>"
        f"<label>Carte capovolte<input type='checkbox' name='TAROT_REVERSED' value='1'{chk('TAROT_REVERSED')}></label>"
        "</fieldset><fieldset><legend>Gioco della vita</legend>"
        f"<label>Nuova generazione ogni (secondi)<input type='number' name='LIFE_SECONDS' min='3' max='3600' value='{e(cfg.str('LIFE_SECONDS'))}'></label>"
        "</fieldset><fieldset><legend>Labirinto</legend>"
        f"<label>Passo del topolino ogni (secondi)<input type='number' name='MAZE_SECONDS' min='3' max='3600' value='{e(cfg.str('MAZE_SECONDS'))}'></label>"
        "</fieldset><button class='pri'>Salva</button></form>"
        f"<footer>Rete {e(cfg.str('AP_SSID'))} · http://10.42.0.1</footer></main></body></html>")
    return "".join(out)


def apply_settings(cfg, form):
    changes = {}
    for key, low in (("MANDEL_SECONDS", 15), ("TAROT_SECONDS", 15),
                     ("LIFE_SECONDS", 3), ("MAZE_SECONDS", 3)):
        try:
            v = int(float(form.get(key, [""])[0]))
        except ValueError:
            continue
        changes[key] = str(max(low, min(3600, v)))
    style = form.get("MANDEL_STYLE", [""])[0]
    if style in STYLES:
        changes["MANDEL_STYLE"] = style
    for key in ("MANDEL_ZOOM_LABEL", "TAROT_REVERSED"):  # checkbox: assente = spenta
        changes[key] = "1" if form.get(key) else "0"
    return changes


class Handler(BaseHTTPRequestHandler):
    ctl = None
    server_version = "etere"

    def log_message(self, fmt, *args):
        log.debug(fmt, *args)

    def _send(self, body, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, msg):
        self.send_response(303)
        self.send_header("Location", "/?ok=" + msg)
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/favicon.ico":
            self.send_response(404)
            self.end_headers()
            return
        # qualunque altro indirizzo (anche i controlli "c'e' internet?" dei
        # telefoni) riceve la pagina: e' cosi' che il telefono la apre da solo
        msg = {"mostra": "Fatto, tra pochi secondi sullo schermo.",
               "foto": "Foto caricata: tra pochi secondi sullo schermo.",
               "avvio": "Salvato: la userà a ogni accensione.",
               "salvato": "Impostazioni salvate."}.get(parse_qs(url.query).get("ok", [""])[0], "")
        self._send(page(self.ctl, msg))

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        path = urlparse(self.path).path
        if path == "/foto":
            return self._photo(n)
        form = parse_qs(self.rfile.read(min(n, 10000)).decode("utf-8", "replace"))
        app = form.get("app", [""])[0]
        if path == "/mostra" and app in apps.APPS:
            self.ctl.show(app)
            return self._redirect("mostra")
        if path == "/predefinita" and app in apps.APPS:
            self.ctl.cfg.save(APP=app)
            return self._redirect("avvio")
        if path == "/impostazioni":
            self.ctl.cfg.save(**apply_settings(self.ctl.cfg, form))
            self.ctl.reload()
            return self._redirect("salvato")
        self._send(page(self.ctl, "Richiesta non valida."), 400)


    def _photo(self, n):
        if n <= 0 or n > foto.MAX_UPLOAD:
            self.close_connection = True
            return self._send(page(self.ctl, "Foto troppo grande (massimo 30 MB)."), 413)
        fields = parse_multipart(self.headers.get("Content-Type", ""), self.rfile.read(n))
        data = fields.get("foto")
        if not data:
            return self._send(page(self.ctl, "Nessuna foto ricevuta."), 400)
        fit = fields.get("fit", b"riempi").decode(errors="replace")
        method = fields.get("dither", b"floyd").decode(errors="replace")
        try:
            img = foto.process(data, fit if fit in foto.FITS else "riempi",
                               method if method in ("floyd", "bayer") else "floyd")
        except foto.PhotoError as e:
            return self._send(page(self.ctl, f"Foto non valida: {e}."), 400)
        finally:
            del data, fields  # l'originale non resta in memoria
        foto.save(self.ctl.cfg, img)
        self.ctl.show("foto")
        return self._redirect("foto")


def parse_multipart(content_type, body):
    """Form multipart/form-data -> {nome campo: byte}. (Il modulo cgi non
    esiste piu' in Python 3.13, quindi usiamo il parser email.)"""
    if not content_type.startswith("multipart/form-data"):
        return {}
    msg = BytesParser(policy=HTTP).parsebytes(
        b"Content-Type: " + content_type.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
    out = {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if name:
            out[name] = part.get_payload(decode=True) or b""
    return out


class Controller:
    """Stato condiviso tra la pagina web e il ciclo che disegna."""

    def __init__(self, cfg, current):
        self.cfg = cfg
        self.current = current
        self.changed = threading.Event()

    def show(self, name):
        self.current = name
        self.changed.set()

    def reload(self):
        self.changed.set()


def start(ctl, port):
    Handler.ctl = ctl
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    except OSError as e:
        log.warning("pagina di controllo non avviata sulla porta %s: %s", port, e)
        return None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log.info("pagina di controllo su http://0.0.0.0:%s", port)
    return srv
