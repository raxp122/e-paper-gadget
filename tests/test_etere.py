"""Test eseguibili ovunque (anche sul PC):  python3 -m unittest discover tests"""
import os
import struct
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "etere"))

import config  # noqa: E402
import render  # noqa: E402
import sources  # noqa: E402
from radiotap import antenna_dbm  # noqa: E402


def radiotap(fields_present, body):
    return struct.pack("<BBHI", 0, 0, 8 + len(body), fields_present) + body


class RadiotapTest(unittest.TestCase):
    def test_solo_segnale(self):
        self.assertEqual(antenna_dbm(radiotap(1 << 5, struct.pack("<b", -57))), -57)

    def test_con_tsft_flags_rate_channel(self):
        present = 0b101111  # tsft, flags, rate, channel, dbm
        body = struct.pack("<QBBHHb", 123, 0, 2, 2437, 0x00A0, -71)
        self.assertEqual(antenna_dbm(radiotap(present, body)), -71)

    def test_allineamento_channel(self):
        # flags (1 byte) + channel allineato a 2 -> 1 byte di padding
        present = (1 << 1) | (1 << 3) | (1 << 5)
        body = struct.pack("<BxHHb", 0, 2412, 0, -40)
        self.assertEqual(antenna_dbm(radiotap(present, body)), -40)

    def test_bitmap_estesa(self):
        present = (1 << 5) | (1 << 31)
        hdr = struct.pack("<BBHII", 0, 0, 13, present, 0) + struct.pack("<b", -33)
        self.assertEqual(antenna_dbm(hdr), -33)

    def test_senza_segnale(self):
        self.assertIsNone(antenna_dbm(radiotap(1 << 1, b"\x00")))
        self.assertIsNone(antenna_dbm(b"\x00\x00"))


SCAN = """BSS 11:22:33:44:55:66(on wlan0)
\tlast seen: 120 ms ago
\tfreq: 2437.0
\tsignal: -54.00 dBm
\tSSID: CasaMia
BSS aa:bb:cc:dd:ee:ff(on wlan0) -- associated
\tfreq: 2412
\tsignal: -80.00 dBm
"""


class ScanTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(sources.parse_iw_scan(SCAN), [(2437.0, -54.0), (2412.0, -80.0)])

    def test_spettro_ha_picco_sul_canale(self):
        col = sources.spectrum_column([(2437, -50)])
        self.assertEqual(col.shape, sources.FREQS.shape)
        self.assertAlmostEqual(sources.FREQS[col.argmax()], 2437, delta=9)
        self.assertGreater(col.max(), col.min() + 30)


class CsiTest(unittest.TestCase):
    def test_parse(self):
        rng = np.random.default_rng(0)
        iq = rng.integers(-500, 500, 128).astype("<i2")
        payload = b"\x11\x11" + bytes(16) + iq.tobytes()
        c = sources.parse_csi(payload)
        self.assertEqual(len(c), 56)

    def test_magic_sbagliato(self):
        self.assertIsNone(sources.parse_csi(b"\x00\x00" + bytes(300)))


class BinTest(unittest.TestCase):
    def test_colonne_vuote_riempite(self):
        m = sources.bin_columns([0.0, 0.95], [[1, 0], [0, 1]], 0, 1, ncols=10)
        self.assertEqual(m.shape, (2, 10))
        self.assertTrue(np.isfinite(m).all())
        self.assertEqual(m[0, 5], 1.0)  # prende il valore precedente


class RenderTest(unittest.TestCase):
    def test_dimensioni_e_modo(self):
        img = render.render(sources.SimSource(seed=1).capture(0))
        self.assertEqual(img.size, (250, 122))
        self.assertEqual(img.mode, "1")

    def test_matrice_costante(self):
        self.assertEqual(render.render(np.zeros((10, 10))).size, (250, 122))

    def test_viste(self):
        m = np.vstack([np.full(20, 5.0), np.r_[np.zeros(10), np.ones(10)]])
        self.assertTrue(np.allclose(render.apply_view(m, "variazioni")[0], 0))
        self.assertTrue((render.apply_view(m, "intensita") >= 0).all())
        for v in render.VIEWS:
            for d in render.DITHERS:
                img = render.render(m, view=v, method=d)
                self.assertEqual((img.size, img.mode), ((250, 122), "1"))
        with self.assertRaises(ValueError):
            render.apply_view(m, "boh")

    def test_bayer_grigio_meta(self):
        from PIL import Image
        img = render.dither(Image.new("L", (64, 64), 128), "bayer")
        black = sum(1 for p in img.getdata() if p == 0)
        self.assertAlmostEqual(black / 4096, 0.5, delta=0.02)

    def test_messaggio(self):
        self.assertEqual(render.message("ciao\nmondo").size, (250, 122))


class ConfigTest(unittest.TestCase):
    def test_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as f:
            f.write("# commento\nsource = scan\nCHANNEL=6  # fisso\nKEEP_WIFI=0\n")
        c = config.Config(path=f.name)
        os.unlink(f.name)
        self.assertEqual(c.str("SOURCE"), "scan")
        self.assertEqual(c.channel(), 6)
        self.assertFalse(c.bool("KEEP_WIFI"))
        self.assertEqual(c.float("EXPOSURE_SECONDS"), 10.0)


if __name__ == "__main__":
    unittest.main()
