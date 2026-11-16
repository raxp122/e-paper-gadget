"""Sorgenti del segnale.

Ogni sorgente "espone" per un certo numero di secondi e restituisce una
matrice 2D (righe x tempo) che poi diventa l'immagine.

  csi   CSI vero via Nexmon CSI (sperimentale: non supportato ufficialmente
        sul chip del Pi Zero W, resta pronto se un giorno lo sara')
  rssi  modalita' monitor su UN canale: densita' delle potenze dei frame
        (righe = livello di segnale in dBm, colonne = tempo)
  scan  ripiego senza modalita' monitor: scansioni Wi-Fi normali
        (righe = frequenza 2400-2490 MHz, colonne = scansioni)
  sim   simulazione per sviluppare sul PC

Nessuna sorgente conserva indirizzi MAC, nomi di rete o contenuti.
"""
import collections
import logging
import re
import shutil
import socket
import struct
import subprocess
import time

import numpy as np

from radiotap import antenna_dbm

log = logging.getLogger("etere.sources")

MON = "mon0"
COLS = 125


class SourceError(RuntimeError):
    pass


def sh(cmd, timeout=15):
    log.debug("$ %s", " ".join(cmd))
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def bin_columns(times, rows, t0, t1, ncols=COLS):
    """Media dei vettori `rows` (uno per campione) in `ncols` fasce di tempo.
    Le fasce vuote prendono il valore della precedente."""
    rows = np.asarray(rows, float)
    out = np.full((rows.shape[1], ncols), np.nan)
    if len(rows):
        idx = np.clip(((np.asarray(times) - t0) / max(t1 - t0, 1e-6) * ncols).astype(int), 0, ncols - 1)
        for c in range(ncols):
            sel = idx == c
            if sel.any():
                out[:, c] = rows[sel].mean(axis=0)
    last = np.nanmean(out) if np.isfinite(out).any() else 0.0
    for c in range(ncols):
        if np.isnan(out[:, c]).all():
            out[:, c] = last if c == 0 else out[:, c - 1]
        else:
            last = out[:, c]
    return np.nan_to_num(out)


# --------------------------------------------------------------------------
# Gestione della radio
# --------------------------------------------------------------------------
class Radio:
    def __init__(self, iface, keep_wifi):
        self.iface = iface
        self.keep_wifi = keep_wifi

    def phy(self):
        r = sh(["iw", "dev", self.iface, "info"])
        m = re.search(r"wiphy (\d+)", r.stdout)
        if not m:
            raise SourceError(f"interfaccia {self.iface} non trovata")
        return "phy" + m.group(1)

    def take(self):
        if not self.keep_wifi:
            log.info("prendo la radio: fermo NetworkManager / wpa_supplicant")
            sh(["systemctl", "stop", "NetworkManager", "wpa_supplicant"], 30)
        sh(["rfkill", "unblock", "wifi"])
        sh(["ip", "link", "set", self.iface, "up"])
        sh(["iw", "dev", self.iface, "set", "power_save", "off"])

    def monitor_up(self):
        if sh(["ip", "link", "show", MON]).returncode != 0:
            r = sh(["iw", "phy", self.phy(), "interface", "add", MON, "type", "monitor"])
            if r.returncode != 0:
                raise SourceError("modalita' monitor non disponibile: " + (r.stderr or r.stdout).strip())
        r = sh(["ip", "link", "set", MON, "up"])
        if r.returncode != 0:
            raise SourceError("impossibile attivare mon0: " + r.stderr.strip())

    def monitor_down(self):
        sh(["iw", "dev", MON, "del"])

    def set_channel(self, ch):
        if self.keep_wifi:
            return False  # il Wi-Fi normale decide il canale
        for cmd in (["iw", "dev", MON, "set", "channel", str(ch)],
                    ["iw", "dev", self.iface, "set", "channel", str(ch)]):
            if sh(cmd).returncode == 0:
                return True
        if shutil.which("nexutil"):
            return sh(["nexutil", f"-I{self.iface}", f"-k{ch}/20"]).returncode == 0
        return False


# --------------------------------------------------------------------------
# rssi: modalita' monitor su un canale
# --------------------------------------------------------------------------
class RssiSource:
    name = "rssi"
    blur = 1.2
    clean_factor = 1.0
    DBM_MIN, DBM_MAX = -96, -20

    def __init__(self, cfg):
        self.radio = Radio(cfg.str("IFACE"), cfg.bool("KEEP_WIFI"))
        self.channel = cfg.channel()
        self.sock = None

    def setup(self):
        self.radio.take()
        self.radio.monitor_up()
        self.sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0003))
        self.sock.bind((MON, 0))
        self.sock.settimeout(0.2)
        if self.channel is None:
            self.channel = self._busiest_channel()
        elif not self.radio.set_channel(self.channel):
            log.warning("non riesco a fissare il canale %s, resto su quello attuale", self.channel)
        log.info("rssi: ascolto sul canale %s", self.channel or "attuale")

    def _listen(self, seconds):
        t, v = [], []
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                pkt = self.sock.recv(4096)
            except socket.timeout:
                continue
            dbm = antenna_dbm(pkt)
            if dbm is not None and -120 < dbm < 0:
                t.append(time.monotonic())
                v.append(dbm)
        return t, v

    def _busiest_channel(self):
        if not self.radio.set_channel(1):
            return None
        counts = {}
        for ch in range(1, 14):
            self.radio.set_channel(ch)
            counts[ch] = len(self._listen(0.35)[1])
        best = max(counts, key=counts.get)
        log.info("frame per canale: %s -> scelgo %s", counts, best)
        self.radio.set_channel(best)
        return best

    def probe(self, seconds=3):
        n = len(self._listen(seconds)[1])
        log.info("rssi: %d frame in %ss", n, seconds)
        return n >= 5

    def capture(self, seconds):
        t0 = time.monotonic()
        t, v = self._listen(seconds)
        t1 = time.monotonic()
        nb = self.DBM_MAX - self.DBM_MIN + 1
        rows = np.zeros((len(v), nb))
        if v:
            b = np.clip(np.asarray(v) - self.DBM_MIN, 0, nb - 1).astype(int)
            rows[np.arange(len(v)), b] = 1.0
        counts = bin_columns(t, rows, t0, t1) * max(len(v), 1) / COLS
        # righe: segnale forte in alto
        return np.log1p(counts[::-1] * 50)

    def close(self):
        if self.sock:
            self.sock.close()
        self.radio.monitor_down()


# --------------------------------------------------------------------------
# scan: ripiego con le scansioni normali (niente modalita' monitor)
# --------------------------------------------------------------------------
FREQS = np.arange(2400, 2491)


def parse_iw_scan(text):
    """Ritorna una lista (freq_MHz, dBm). Ignora volutamente indirizzi e nomi."""
    out, freq, sig = [], None, None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("BSS ") and "(on " in s:
            if freq is not None and sig is not None:
                out.append((freq, sig))
            freq = sig = None
        elif s.startswith("freq:"):
            try:
                freq = float(s.split()[1])
            except (IndexError, ValueError):
                pass
        elif s.startswith("signal:"):
            try:
                sig = float(s.split()[1])
            except (IndexError, ValueError):
                pass
    if freq is not None and sig is not None:
        out.append((freq, sig))
    return out


def spectrum_column(aps):
    """Spettro in dB su 2400-2490 MHz: ogni rete col suo profilo OFDM da 20 MHz."""
    lin = np.full(FREQS.shape, 10 ** (-100 / 10))
    for f, dbm in aps:
        if not 2400 <= f <= 2500:
            continue
        d = np.abs(FREQS - f)
        mask_db = np.select([d <= 9, d <= 11, d <= 20, d <= 30],
                            [0, -20 * (d - 9) / 2, -28, -40], -60)
        lin += 10 ** ((dbm + mask_db) / 10)
    return 10 * np.log10(lin)


def smooth_scans(m):
    """Massimo su 3 scansioni vicine: copre le reti 'perse' da una scansione."""
    p = np.pad(m, ((0, 0), (1, 1)), mode="edge")
    return np.maximum(np.maximum(p[:, :-2], p[:, 1:-1]), p[:, 2:])


class ScanSource:
    name = "scan"
    blur = 0.8
    clean_factor = 0.0  # le scansioni rendono meglio morbide

    def __init__(self, cfg):
        self.iface = cfg.str("IFACE")
        self.history = collections.deque(maxlen=48)

    def setup(self):
        sh(["rfkill", "unblock", "wifi"])
        sh(["ip", "link", "set", self.iface, "up"])

    def _scan(self):
        for attempt in range(3):
            cmd = ["iw", "dev", self.iface, "scan"]
            if attempt == 2:
                cmd.append("ap-force")  # quando il gadget fa da rete, se il driver lo permette
            r = sh(cmd, 20)
            if r.returncode == 0:
                return parse_iw_scan(r.stdout)
            time.sleep(1)  # spesso "Device or resource busy": riprovo
        return None

    def probe(self, seconds=0):
        aps = self._scan()
        log.info("scan: %s reti visibili", None if aps is None else len(aps))
        if aps is not None:
            self.history.append(spectrum_column(aps))
        return aps is not None

    def capture(self, seconds):
        end = time.monotonic() + seconds
        while True:
            aps = self._scan()
            if aps is not None:
                self.history.append(spectrum_column(aps))
            if time.monotonic() >= end:
                break
        cols = list(self.history) or [spectrum_column([])]
        if len(cols) == 1:
            cols = cols * 2
        return smooth_scans(np.array(cols).T)

    def close(self):
        pass


# --------------------------------------------------------------------------
# csi: Nexmon CSI (sperimentale sul Pi Zero W)
# --------------------------------------------------------------------------
def parse_csi(payload):
    """Payload UDP di Nexmon CSI -> vettore complesso (sottoportanti utili)."""
    if len(payload) < 16 + 256 or payload[:2] != b"\x11\x11":
        return None
    for hdr in (18, 16, 14):
        n4 = len(payload) - hdr
        if n4 in (256, 512, 1024):
            break
    else:
        return None
    raw = np.frombuffer(payload[hdr:], dtype="<i2").astype(float)
    csi = np.fft.fftshift(raw[0::2] + 1j * raw[1::2])
    n = len(csi)
    k = np.arange(n) - n // 2
    if n == 64:
        keep = (np.abs(k) <= 28) & (k != 0)   # 802.11n 20 MHz: 56 utili
    else:
        keep = (np.abs(k) <= n // 2 - 5) & (np.abs(k) > 1)
    return csi[keep]


class CsiSource:
    name = "csi"
    blur = 0.0
    clean_factor = 1.0

    def __init__(self, cfg):
        self.cfg = cfg
        self.radio = Radio(cfg.str("IFACE"), keep_wifi=False)
        self.channel = cfg.channel() or 6
        self.sock = None

    def setup(self):
        if not (shutil.which("nexutil") and shutil.which("makecsiparams")):
            raise SourceError("nexutil/makecsiparams non installati")
        p = sh(["makecsiparams", "-c", f"{self.channel}/20", "-C", "1", "-N", "1"])
        params = p.stdout.strip()
        if p.returncode or not params:
            raise SourceError("makecsiparams fallito")
        self.radio.take()
        r = sh(["nexutil", f"-I{self.radio.iface}", "-s500", "-b", "-l34", f"-v{params}"])
        if r.returncode:
            raise SourceError("nexutil fallito: " + r.stderr.strip())
        self.radio.monitor_up()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", 5500))
        self.sock.settimeout(0.2)

    def _listen(self, seconds):
        t, v = [], []
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                continue
            c = parse_csi(data)
            if c is not None and (not v or len(c) == len(v[0])):
                t.append(time.monotonic())
                v.append(np.log1p(np.abs(c)))
        return t, v

    def probe(self, seconds=3):
        n = len(self._listen(seconds)[1])
        log.info("csi: %d pacchetti in %ss", n, seconds)
        return n >= 5

    def capture(self, seconds):
        t0 = time.monotonic()
        t, v = self._listen(seconds)
        if not v:
            return np.zeros((56, COLS))
        return bin_columns(t, v, t0, time.monotonic())

    def close(self):
        if self.sock:
            self.sock.close()
        self.radio.monitor_down()


# --------------------------------------------------------------------------
# sim: simulazione fisicamente plausibile (solo per sviluppo)
# --------------------------------------------------------------------------
class SimSource:
    name = "sim"
    blur = 0.0
    clean_factor = 1.0

    def __init__(self, cfg=None, seed=None):
        self.rng = np.random.default_rng(seed)

    def setup(self):
        pass

    def probe(self, seconds=0):
        return True

    def capture(self, seconds):
        rng = self.rng
        n_sub, n_time = 56, 250
        f = np.linspace(-1, 1, n_sub)
        t = np.arange(n_time)
        nt = rng.integers(4, 9)
        tau = rng.uniform(0, 9, nt)
        amp = rng.uniform(.3, 1, nt) * np.exp(-tau / 5)
        phi = rng.uniform(0, 2 * np.pi, nt)
        dr = rng.uniform(-.04, .04, nt)
        h = np.zeros((n_sub, n_time), complex)
        for k in range(nt):
            h += amp[k] * np.exp(1j * (2 * np.pi * tau[k] * f[:, None] + phi[k] + dr[k] * t[None, :]))
        if rng.random() < .8:
            w0 = rng.integers(20, n_time - 70)
            mv = (t >= w0) & (t < w0 + rng.integers(30, 70))
            fast = np.exp(1j * (2 * np.pi * rng.uniform(2, 6) * f[:, None] + rng.uniform(.4, .9) * t[None, :]))
            h[:, mv] += rng.uniform(.6, 1.1) * fast[:, mv]
        h += rng.normal(0, .08, h.shape) + 1j * rng.normal(0, .08, h.shape)
        return np.log1p(np.abs(h))

    def close(self):
        pass


SOURCES = {"csi": CsiSource, "rssi": RssiSource, "scan": ScanSource, "sim": SimSource}


def choose(cfg):
    want = cfg.str("SOURCE").strip().lower()
    order = ["csi", "rssi", "scan"] if want == "auto" else [want]
    errors = []
    for name in order:
        if name not in SOURCES:
            raise SourceError(f"sorgente sconosciuta: {name}")
        src = SOURCES[name](cfg)
        try:
            src.setup()
            if src.probe():
                log.info("sorgente scelta: %s", name)
                return src
            errors.append(f"{name}: nessun segnale")
        except (SourceError, OSError) as e:
            errors.append(f"{name}: {e}")
        try:
            src.close()
        except Exception:
            pass
        log.info("scarto %s", errors[-1])
    raise SourceError("; ".join(errors))
