"""Test eseguibili ovunque (anche sul PC):  python3 -m unittest discover tests"""
import os
import struct
import subprocess
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


class SaveTest(unittest.TestCase):
    def test_aggiorna_e_aggiunge(self):
        with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as f:
            f.write("# commento\nAPP=tarocchi  # nota\nX=1\n")
        c = config.Config(path=f.name)
        c.save(APP="mandelbrot", TAROT_SECONDS=45)
        text = open(f.name).read()
        os.unlink(f.name)
        self.assertIn("# commento", text)
        self.assertIn("APP=mandelbrot", text)
        self.assertIn("TAROT_SECONDS=45", text)
        self.assertEqual(c.str("APP"), "mandelbrot")


class TarocchiTest(unittest.TestCase):
    def test_mazzo_completo(self):
        from apps import tarocchi as T
        deck = T.load_deck()
        self.assertEqual(len(deck), 78)
        self.assertEqual(sum("maggiore" in c["head"] for c in deck), 22)
        self.assertEqual(len({c["img"] for c in deck}), 78)
        for c in deck:
            self.assertEqual((len(c["up"]), len(c["rev"])), (3, 3), c["name"])

    def test_tutte_le_carte_entrano_nello_schermo(self):
        from PIL import Image, ImageDraw
        from apps import tarocchi as T
        d = ImageDraw.Draw(Image.new("1", (250, 122)))
        for c in T.load_deck():
            for rev in (False, True):
                *_, total, widest = T.fit(d, c, rev)
                self.assertLessEqual(total, T.H, c["name"])
                self.assertLessEqual(widest, T.TEXT_W, c["name"])

    def test_frame(self):
        from apps import tarocchi as T
        img, wait = T.TarocchiApp(config.Config(path=os.devnull)).frame()
        self.assertEqual((img.size, img.mode, wait), ((250, 122), "1", 30.0))


class MandelbrotTest(unittest.TestCase):
    def test_viaggio(self):
        from apps import mandelbrot as M
        j = M.Journey("incisione")
        for _ in range(8):
            g, depth = j.frame()
            self.assertEqual(g.shape, (122, 250))
        self.assertGreater(depth, 50)          # e' sceso in profondita'
        self.assertLess(j.half_width, M.START_HALF_WIDTH)

    def test_stili(self):
        from apps import mandelbrot as M
        nu, ins, dist = M.compute(M.START_CENTER, M.START_HALF_WIDTH, 60)
        self.assertTrue(ins.any() and (~ins).any())
        for s in M.STYLES:
            g = M.stylize(nu, ins, dist, M.START_HALF_WIDTH, s)
            self.assertTrue(((g >= 0) & (g <= 1)).all())


class FotoTest(unittest.TestCase):
    def _jpeg(self, size, orientation=None):
        import io
        from PIL import Image
        im = Image.new("RGB", size, (120, 120, 120))
        buf = io.BytesIO()
        if orientation:
            ex = im.getexif()
            ex[0x0112] = orientation
            im.save(buf, "JPEG", exif=ex)
        else:
            im.save(buf, "JPEG")
        return buf.getvalue()

    def test_elabora(self):
        from apps import foto
        for fit in foto.FITS:
            for method in ("floyd", "bayer"):
                img = foto.process(self._jpeg((3000, 4000), 6), fit, method)
                self.assertEqual((img.size, img.mode), ((250, 122), "1"))

    def test_file_non_valido(self):
        from apps import foto
        with self.assertRaises(foto.PhotoError):
            foto.process(b"non sono una foto")

    def test_salva_e_mostra_sovrascrivendo(self):
        from apps import foto
        d = tempfile.mkdtemp()
        conf = os.path.join(d, "etere.conf")
        open(conf, "w").close()
        cfg = config.Config(path=conf)
        for _ in range(3):
            foto.save(cfg, foto.process(self._jpeg((800, 600))))
        self.assertEqual(sorted(os.listdir(d)), ["etere-foto.png", "etere.conf"])
        img, wait = foto.FotoApp(cfg).frame()
        self.assertEqual(img.size, (250, 122))

    def test_multipart(self):
        import web
        body = (b"--XX\r\nContent-Disposition: form-data; name=\"fit\"\r\n\r\nintera\r\n"
                b"--XX\r\nContent-Disposition: form-data; name=\"foto\"; filename=\"a.jpg\"\r\n"
                b"Content-Type: image/jpeg\r\n\r\n\x00\x01\r\n\xffDATA\r\n--XX--\r\n")
        f = web.parse_multipart("multipart/form-data; boundary=XX", body)
        self.assertEqual(f["fit"], b"intera")
        self.assertEqual(f["foto"], b"\x00\x01\r\n\xffDATA")


class VitaTest(unittest.TestCase):
    def test_regole(self):
        from apps.vita import step
        g = np.zeros((6, 6), np.uint8)
        g[2, 1:4] = 1                                   # lampeggiatore: periodo 2
        self.assertFalse((step(g) == g).all())
        self.assertTrue((step(step(g)) == g).all())
        b = np.zeros((6, 6), np.uint8)
        b[2:4, 2:4] = 1                                 # blocco: fermo
        self.assertTrue((step(b) == b).all())

    def test_si_stabilizza_e_riparte(self):
        from apps.vita import VitaApp, HOLD
        app = VitaApp(config.Config({"LIFE_MAX_GEN": "6"}, path=os.devnull))
        for _ in range(6 + HOLD + 1):
            img, wait = app.frame()
        self.assertEqual((img.size, wait), ((250, 122), 5.0))
        self.assertLess(app.gen, 6)                     # e' ripartito da capo


class LabirintoTest(unittest.TestCase):
    def test_labirinto_perfetto(self):
        import random
        from apps.labirinto import generate
        rows, cols = 12, 20
        op = generate(rows, cols, random.Random(1))
        self.assertEqual(len(op) // 2, rows * cols - 1)  # albero: un solo percorso
        seen, todo = {(0, 0)}, [(0, 0)]
        while todo:
            a = todo.pop()
            for x, b in op:
                if x == a and b not in seen:
                    seen.add(b)
                    todo.append(b)
        self.assertEqual(len(seen), rows * cols)         # tutto raggiungibile

    def test_trova_uscita_e_ricomincia(self):
        from apps.labirinto import LabirintoApp, HOLD
        app = LabirintoApp(config.Config({"MAZE_STEPS": "50"}, path=os.devnull))
        for _ in range(500):
            img, _ = app.frame()
            if app.done:
                break
        self.assertTrue(app.done)
        self.assertEqual(app.stack[-1], app.exit)
        self.assertEqual(img.size, (250, 122))
        for _ in range(HOLD + 1):
            app.frame()
        self.assertFalse(app.done)                       # labirinto nuovo


class DisplayTest(unittest.TestCase):
    def test_parziali_e_completi(self):
        import display

        class FakeEpd:
            FULL_UPDATE = 0

            def __init__(self):
                self.calls = []

            def init(self):
                self.calls.append("init")

            def getbuffer(self, img):
                return b""

            def display(self, b):
                self.calls.append("full")

            def displayPartBaseImage(self, b):
                self.calls.append("base")

            def displayPartial(self, b):
                self.calls.append("partial")

            def sleep(self):
                self.calls.append("sleep")

        d = display.EpdDisplay.__new__(display.EpdDisplay)
        d.epd, d.model, d.full_every, d.awake, d.partials, d.can_partial = FakeEpd(), "V3", 3, False, 0, True
        img = render.message("x")
        for _ in range(5):
            d.show(img, partial=True)
        d.show(img, partial=True, reset=True)
        d.show(img)                                      # app lenta: completo + sleep
        c = [x for x in d.epd.calls if x != "init"]
        self.assertEqual(c, ["base", "partial", "partial", "partial", "base", "base", "full", "sleep"])
        self.assertFalse(d.awake)


class ReteTest(unittest.TestCase):
    def _fake(self, states):
        calls = []
        seq = iter(states)

        def run(cmd, timeout=60):
            calls.append(cmd)
            if cmd[:2] == ["nmcli", "-t"]:
                st = next(seq, states[-1])
                return subprocess.CompletedProcess(cmd, 0, f"eth0:unavailable\nwlan0:{st}\n", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        t = [0.0]

        def sleep(s):
            t[0] += s
        return run, sleep, (lambda: t[0]), calls

    def test_hotspot_trovato(self):
        import rete
        run, sleep, clock, calls = self._fake(["connecting", "connected"])
        self.assertEqual(rete.fallback("wlan0", 45, run, sleep, clock), "client")
        self.assertNotIn(["nmcli", "connection", "up", rete.AP], calls)

    def test_nessuna_rete_accende_la_propria(self):
        import rete
        run, sleep, clock, calls = self._fake(["disconnected"])
        self.assertEqual(rete.fallback("wlan0", 45, run, sleep, clock), "ap")
        self.assertEqual(calls[-1], ["nmcli", "connection", "up", rete.AP])


class WebTest(unittest.TestCase):
    def test_pagina_e_impostazioni(self):
        import web
        cfg = config.Config(path=os.devnull)
        page = web.page(web.Controller(cfg, "tarocchi"), "ok")
        self.assertIn("Tarocchi", page)
        self.assertIn("/mostra", page)
        self.assertEqual(web.apply_settings(cfg, {"LIFE_SECONDS": ["1"]})["LIFE_SECONDS"], "3")
        ch = web.apply_settings(cfg, {"MANDEL_SECONDS": ["5"], "TAROT_SECONDS": ["99999"],
                                      "MANDEL_STYLE": ["china"], "TAROT_REVERSED": ["1"]})
        self.assertEqual(ch["MANDEL_SECONDS"], "15")
        self.assertEqual(ch["TAROT_SECONDS"], "3600")
        self.assertEqual(ch["MANDEL_STYLE"], "china")
        self.assertEqual((ch["TAROT_REVERSED"], ch["MANDEL_ZOOM_LABEL"]), ("1", "0"))
        self.assertNotIn("MANDEL_STYLE", web.apply_settings(cfg, {"MANDEL_STYLE": ["<x>"]}))


if __name__ == "__main__":
    unittest.main()
