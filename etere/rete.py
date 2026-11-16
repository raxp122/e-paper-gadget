"""Rete del gadget.

All'accensione aspetta una rete conosciuta (per esempio l'hotspot del
telefono). Se non arriva, accende la rete "raspberry" del gadget. Mentre la
rete del gadget e' accesa, ogni tanto, se nessuno e' collegato, la spegne per
un momento e riprova le reti conosciute. E se l'hotspot sparisce mentre il
gadget e' in uso, dopo l'attesa riaccende la rete del gadget.

Non ci affidiamo alla scelta automatica di NetworkManager: se la rete
dell'hotspot e' segnata come "nascosta" la considera sempre disponibile e
continua a cercarla. E l'iPhone mostra l'hotspot solo mentre la schermata
"Hotspot personale" e' aperta o qualcuno e' gia' collegato.
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
    """(stato, connessione attiva) secondo NetworkManager, es. ('connected', 'etere-ap')."""
    r = run(["nmcli", "-t", "-f", "DEVICE,STATE,CONNECTION", "device"])
    for line in r.stdout.splitlines():
        parts = line.split(":", 2)
        if parts[0] == iface:
            return (parts[1] if len(parts) > 1 else ""), (parts[2] if len(parts) > 2 else "")
    return "", ""


def mode(iface, run=_run):
    """'client' (collegato a una rete conosciuta), 'ap' (rete del gadget) o ''."""
    state, conn = wifi_state(iface, run)
    if not state.startswith("connected"):
        return ""
    return "ap" if conn == AP else "client"


def ap_clients(iface, run=_run):
    """Quanti dispositivi sono collegati alla rete del gadget (solo il numero)."""
    r = run(["iw", "dev", iface, "station", "dump"])
    return sum(1 for line in r.stdout.splitlines() if line.startswith("Station "))


def wait_client(iface, wait, run, sleep, clock):
    end = clock() + wait
    while clock() < end:
        if mode(iface, run) == "client":
            return True
        sleep(3)
    return False


def supervise(iface="wlan0", wait=90, retry=300, run=_run, sleep=time.sleep,
              clock=time.monotonic, rounds=None):
    """Ciclo infinito (o `rounds` giri, per i test). Ritorna la lista degli
    eventi, utile per i test: 'client', 'ap', 'riprovo', 'errore'."""
    events = []
    while rounds is None or len(events) < rounds:
        now = mode(iface, run)
        if now == "client" or (now != "ap" and wait_client(iface, wait, run, sleep, clock)):
            if not events or events[-1] != "client":
                log.info("collegato a una rete conosciuta")
                events.append("client")
            while mode(iface, run) == "client":      # finche' resta collegato
                sleep(30)
                if rounds is not None:
                    break
            continue
        if now != "ap":
            log.info("nessuna rete conosciuta dopo %ss: accendo la rete del gadget", wait)
            r = run(["nmcli", "connection", "up", AP])
            if r.returncode != 0:
                log.error("rete del gadget non avviata: %s", (r.stderr or r.stdout).strip())
                events.append("errore")
                sleep(retry)
                continue
        events.append("ap")
        sleep(retry)
        if ap_clients(iface, run) == 0:
            log.info("nessuno collegato alla rete del gadget: riprovo le reti conosciute")
            run(["nmcli", "connection", "down", AP])
            events.append("riprovo")
    return events


def start_fallback(cfg):
    if not shutil.which("nmcli"):
        return None
    t = threading.Thread(target=supervise, daemon=True,
                         args=(cfg.str("IFACE"), cfg.float("AP_FALLBACK_SECONDS"),
                               cfg.float("AP_RETRY_SECONDS")))
    t.start()
    return t
