"""Le app del gadget. Ognuna ha `name`, `title`, `frame()` -> (immagine 1-bit
250x122, secondi di attesa prima del prossimo frame) e `close()`.
Per aggiungerne una: scrivere il modulo e registrarla in APPS."""
from apps.foto import FotoApp
from apps.mandelbrot import MandelbrotApp
from apps.radio import RadioApp
from apps.tarocchi import TarocchiApp

APPS = {a.name: a for a in (MandelbrotApp, TarocchiApp, FotoApp, RadioApp)}


def create(name, cfg):
    if name not in APPS:
        raise KeyError(name)
    return APPS[name](cfg)
