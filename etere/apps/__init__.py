"""Le app del gadget. Ognuna ha `name`, `title`, `frame()` -> (immagine 1-bit
250x122, secondi di attesa prima del prossimo frame) e `close()`.
Facoltativi: `partial = True` (aggiornamenti veloci senza lampeggio) e
`reset_next = True` (chiede un refresh completo per il prossimo frame).
Per aggiungerne una: scrivere il modulo e registrarla in APPS."""
from apps.foto import FotoApp
from apps.labirinto import LabirintoApp
from apps.mandelbrot import MandelbrotApp
from apps.radio import RadioApp
from apps.tarocchi import TarocchiApp
from apps.vita import VitaApp

APPS = {a.name: a for a in (MandelbrotApp, TarocchiApp, VitaApp, LabirintoApp, FotoApp, RadioApp)}


def create(name, cfg):
    if name not in APPS:
        raise KeyError(name)
    return APPS[name](cfg)
