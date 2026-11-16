"""Rete del gadget: se all'accensione il Wi-Fi non si collega a nessuna rete
conosciuta (per esempio l'hotspot del telefono e' spento), accende la rete
"raspberry" del gadget.

Non ci affidiamo alla scelta automatica di NetworkManager: se la rete
dell'hotspot e' segnata come "nascosta" la considera sempre disponibile e
continua a cercarla, e comunque riprova a lungo prima di arrendersi.
"""
import logging
import shutil
import subprocess
import threading
import time

log = logging.getLogger("etere.rete")
AP = "etere-ap"


def _run(cmd, timeout=60):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def wifi_state(iface, run=_run):
    """Stato di NetworkManager per l'interfaccia (es. 'connected')."""
    r = run(["nmcli", "-t", "-f", "DEVICE,STATE", "device"])
    for line in r.stdout.splitlines():
        dev, _, state = line.partition(":")
        if dev == iface:
            return state
    return ""


def fallback(iface="wlan0", wait=45, run=_run, sleep=time.sleep, clock=time.monotonic):
    """Aspetta `wait` secondi una rete conosciuta; se non arriva, accende la
    rete del gadget. Ritorna 'client', 'ap' o 'errore'."""
    end = clock() + wait
    while clock() < end:
        if wifi_state(iface, run).startswith("connected"):
            log.info("collegato a una rete conosciuta: niente rete del gadget")
            return "client"
        sleep(3)
    log.info("nessuna rete conosciuta dopo %ss: accendo la rete del gadget", wait)
    r = run(["nmcli", "connection", "up", AP])
    if r.returncode == 0:
        log.info("rete del gadget attiva")
        return "ap"
    log.error("rete del gadget non avviata: %s", (r.stderr or r.stdout).strip())
    return "errore"


def start_fallback(cfg):
    if not shutil.which("nmcli"):
        return None
    t = threading.Thread(target=fallback, daemon=True,
                         args=(cfg.str("IFACE"), cfg.float("AP_FALLBACK_SECONDS")))
    t.start()
    return t
