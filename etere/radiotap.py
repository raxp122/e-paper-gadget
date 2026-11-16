"""Lettura minima dell'intestazione radiotap.

Da ogni frame catturato in modalita' monitor estraiamo SOLO la potenza del
segnale (dBm). Non leggiamo indirizzi, nomi di rete o contenuti: l'opera
usa l'energia dell'etere, non l'identita' di chi la emette.
"""
import struct

# bit -> (dimensione, allineamento) dei campi che precedono "antenna signal"
_FIELDS = {
    0: (8, 8),  # TSFT
    1: (1, 1),  # flags
    2: (1, 1),  # rate
    3: (4, 2),  # channel (freq u16 + flags u16)
    4: (2, 1),  # FHSS
    5: (1, 1),  # dBm antenna signal (s8)
}
_EXT = 1 << 31


def antenna_dbm(pkt):
    """Ritorna la potenza in dBm (int) o None se assente/illeggibile."""
    if len(pkt) < 8 or pkt[0] != 0:
        return None
    it_len = struct.unpack_from("<H", pkt, 2)[0]
    if it_len > len(pkt):
        return None
    present = struct.unpack_from("<I", pkt, 4)[0]
    if not present & (1 << 5):
        return None
    off = 8
    word = present
    while word & _EXT:  # salta eventuali bitmap estese
        if off + 4 > it_len:
            return None
        word = struct.unpack_from("<I", pkt, off)[0]
        off += 4
    for bit in range(6):
        if not present & (1 << bit):
            continue
        size, align = _FIELDS[bit]
        off = (off + align - 1) & ~(align - 1)
        if off + size > it_len:
            return None
        if bit == 5:
            return struct.unpack_from("<b", pkt, off)[0]
        off += size
    return None
