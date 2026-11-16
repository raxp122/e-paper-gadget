"""Configurazione di Etere.

I valori di default stanno qui. Si possono cambiare scrivendo righe
CHIAVE=valore nel file etere.conf sulla partizione di boot della SD
(/boot/firmware/etere.conf), che si apre anche dal PC con un lettore di SD.
"""
import os

BOOT_DIRS = ("/boot/firmware", "/boot")

DEFAULTS = {
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
    "VIEW": "variazioni",
    # Dithering: floyd (morbido) | bayer (a reticolo, tipo incisione)
    "DITHER": "floyd",
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

    def channel(self):
        v = self.values["CHANNEL"].strip().lower()
        return None if v == "auto" else int(v)
