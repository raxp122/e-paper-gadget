"""Configurazione di Etere.

I valori di default stanno qui. Si possono cambiare scrivendo righe
CHIAVE=valore nel file etere.conf sulla partizione di boot della SD
(/boot/firmware/etere.conf), che si apre anche dal PC con un lettore di SD.
"""
import os

BOOT_DIRS = ("/boot/firmware", "/boot")

DEFAULTS = {
    # App mostrata all'accensione: mandelbrot | tarocchi | vita | labirinto | foto | etere
    "APP": "mandelbrot",
    # --- Mandelbrot ---
    "MANDEL_SECONDS": "60",
    # stile: incisione | china | chiaroscuro
    "MANDEL_STYLE": "incisione",
    # 1 = mostra l'ingrandimento nell'angolo
    "MANDEL_ZOOM_LABEL": "1",
    # --- Tarocchi ---
    "TAROT_SECONDS": "30",
    # 1 = le carte possono uscire capovolte (meta' delle volte)
    "TAROT_REVERSED": "1",
    # --- Gioco della vita ---
    "LIFE_SECONDS": "5",
    "LIFE_DENSITY": "0.3",
    # lato di una cella in pixel
    "LIFE_CELL": "3",
    # dopo tante generazioni riparte comunque (gli alianti possono girare per sempre)
    "LIFE_MAX_GEN": "1000",
    "LIFE_LABEL": "1",
    # --- Labirinto ---
    "MAZE_SECONDS": "5",
    # passi del topolino per ogni aggiornamento
    "MAZE_STEPS": "12",
    # lato di una cella in pixel
    "MAZE_CELL": "6",
    # --- Display ---
    # con gli aggiornamenti parziali, un refresh completo ogni tanti frame
    "EPD_FULL_EVERY": "30",
    # --- Rete del gadget e pagina di controllo ---
    "AP_SSID": "raspberry",
    # almeno 8 caratteri (regola del Wi-Fi WPA2)
    "AP_PASSWORD": "raspberrypi",
    "WEB_PORT": "80",
    # --- Etere (onde Wi-Fi) ---
    # Da dove arriva il segnale: auto | csi | rssi | scan | sim
    "SOURCE": "auto",
    # Canale Wi-Fi da ascoltare (1-13) oppure auto = il piu' trafficato
    "CHANNEL": "auto",
    # Secondi di "esposizione": lo schermo resta fermo e intanto si ascolta
    "EXPOSURE_SECONDS": "10",
    # Esposizione del primo scatto dopo l'accensione
    "FIRST_EXPOSURE_SECONDS": "5",
    # Quanto ripulire l'immagine: 0 = grezza, 1 = molto pulita
    "CLEAN": "0.6",
    # Come guardare il segnale: spettro | variazioni | intensita | mix
    "VIEW": "intensita",
    # Dithering: floyd (morbido) | bayer (a reticolo, tipo incisione)
    "DITHER": "bayer",
    # Versione del pannello: V2 | V3 | V4 (vedi etichetta sul retro)
    "EPD": "V3",
    # 1 = inverte bianco e nero
    "INVERT": "0",
    # 0 oppure 180 (se il display e' montato capovolto)
    "ROTATE": "0",
    # 1 = non spegne il Wi-Fi normale (utile per lavorare via SSH),
    # 0 = il gadget si prende la radio tutta per se' (cattura piu' pura)
    "KEEP_WIFI": "1",
    # Interfaccia Wi-Fi fisica
    "IFACE": "wlan0",
}


def find_boot_file(name):
    for d in BOOT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def parse(text):
    out = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip().upper()] = v.strip().strip('"').strip("'")
    return out


class Config:
    def __init__(self, overrides=None, path=None):
        self.values = dict(DEFAULTS)
        path = path or find_boot_file("etere.conf")
        self.path = path
        if path:
            with open(path, encoding="utf-8") as f:
                self.values.update(parse(f.read()))
        if overrides:
            self.values.update({k.upper(): str(v) for k, v in overrides.items()})

    def str(self, key):
        return self.values[key]

    def float(self, key):
        return float(self.values[key])

    def bool(self, key):
        return self.values[key].strip().lower() in ("1", "true", "yes", "si", "sì", "on")

    def save(self, **changes):
        """Cambia valori in memoria e, se c'e' un file, anche sul file."""
        self.values.update({k.upper(): str(v) for k, v in changes.items()})
        if self.path and self.path != os.devnull:
            save_values(self.path, changes)

    def data_path(self, name):
        """Dove salvare un piccolo file che deve sopravvivere ai riavvii: accanto
        a etere.conf (partizione di boot), altrimenti nella cartella data."""
        if self.path and self.path != os.devnull:
            return os.path.join(os.path.dirname(os.path.abspath(self.path)), name)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", name)

    def channel(self):
        v = self.values["CHANNEL"].strip().lower()
        return None if v == "auto" else int(v)


def _boot_mount(path):
    """Se il file sta sulla partizione di boot montata in sola lettura,
    ritorna il punto di montaggio (da riaprire in scrittura un attimo)."""
    for d in BOOT_DIRS:
        if path.startswith(d + "/") and os.path.ismount(d):
            return d
    return None


def save_values(path, changes):
    """Aggiorna o aggiunge righe CHIAVE=valore mantenendo commenti e ordine."""
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    todo = {k.upper(): str(v) for k, v in changes.items()}
    for i, raw in enumerate(lines):
        key = raw.split("#", 1)[0].split("=", 1)[0].strip().upper()
        if "=" in raw.split("#", 1)[0] and key in todo:
            lines[i] = f"{key}={todo.pop(key)}"
    lines += [f"{k}={v}" for k, v in todo.items()]
    write_file(path, ("\n".join(lines) + "\n").encode("utf-8"))


def write_file(path, data):
    """Scrive un file in modo atomico. Se sta sulla partizione di boot in sola
    lettura, la riapre in scrittura solo per il tempo della scrittura."""
    import subprocess
    mnt = _boot_mount(path)
    remounted = False
    if mnt and not os.access(mnt, os.W_OK):
        remounted = subprocess.run(["mount", "-o", "remount,rw", mnt]).returncode == 0
    try:
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        os.sync()
    finally:
        if remounted:
            subprocess.run(["mount", "-o", "remount,ro", mnt])
