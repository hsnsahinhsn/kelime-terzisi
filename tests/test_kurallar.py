"""Her kuralın "yakalamalı" ve "yakalamamalı" örnekleri otomatik denenir."""
import unittest

from terzi.denetci import denetle, kurallar


def _tur(k):
    return k.turler[0] if k.turler else "genel"


class KuralOrnekleri(unittest.TestCase):
    def test_kural_sayisi(self):
        self.assertGreater(len(kurallar()), 10)

    def test_her_kuralin_ornegi_var(self):
        for k in kurallar():
            with self.subTest(k.kimlik):
                self.assertTrue(k.yakalamali, "yakalamalı örnek yok")
                self.assertTrue(k.yakalamamali, "yakalamamalı örnek yok")
                self.assertTrue(k.kaynak, "kaynak yok")
                self.assertTrue(k.oneri, "öneri yok")

    def test_yakalamali(self):
        for k in kurallar():
            for ornek in k.yakalamali:
                with self.subTest(k.kimlik, ornek=ornek[:60]):
                    r = denetle(ornek, _tur(k), secili={k.kimlik}, yol="dar")
                    self.assertTrue(r.bulgular, f"{k.kimlik} yakalamadı")

    def test_yakalamamali(self):
        for k in kurallar():
            for ornek in k.yakalamamali:
                with self.subTest(k.kimlik, ornek=ornek[:60]):
                    r = denetle(ornek, _tur(k), secili={k.kimlik}, yol="dar")
                    self.assertFalse(r.bulgular, f"{k.kimlik} yanlış alarm: {[b.alinti for b in r.bulgular]}")


if __name__ == "__main__":
    unittest.main()
