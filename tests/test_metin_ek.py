import unittest

from terzi import ek
from terzi.metin import coz, kucuk, sade


class Metin(unittest.TestCase):
    def test_kucuk_harf(self):
        self.assertEqual(kucuk("IŞIK İzmir"), "ışık izmir")
        self.assertEqual(sade("Hâlâ Kâr"), "hala kar")

    def test_cumle_bolme(self):
        b = coz("Dr. Ahmet 1. Dünya Savaşı'nı anlattı. Sonra döndü! Peki ya biz? M. Kemal geldi.")
        self.assertEqual([c.yazi for c in b.cumleler],
                         ["Dr. Ahmet 1. Dünya Savaşı'nı anlattı.", "Sonra döndü!", "Peki ya biz?", "M. Kemal geldi."])

    def test_konusma_ve_kod(self):
        b = coz("— Nereye? dedi.\n— Eve.\n\nKod `a.b()` ve https://x.org/a.b burada.")
        self.assertEqual([bl.tur for bl in b.bloklar], ["diyalog", "diyalog", "paragraf"])
        self.assertEqual(len(b.bloklar[2].cumleler), 1)
        self.assertNotIn("x", [k.yazi for k in b.bloklar[2].cumleler[0].kelimeler])

    def test_konumlar_ozgun_metne_isaret_eder(self):
        t = "İlk cümle. İkinci CÜMLE burada."
        for c in coz(t).cumleler:
            self.assertEqual(t[c.bas:c.son], c.yazi)
            for k in c.kelimeler:
                self.assertEqual(t[k.bas:k.son], k.yazi)


class Ek(unittest.TestCase):
    def sinif(self, w):
        return ek.son_sinif(w, "dar")

    def test_cumle_sonu(self):
        beklenen = {"gelmektedir": "mAktAdIr", "yapılmıştır": "mIştIr", "önemlidir": "DIr", "sahiptir": "DIr",
                    "geliyor": "Iyor", "geldi": "DI", "geliyordu": "DI", "gelmiş": "mIş", "gelecekler": "AcAk",
                    "gelmeli": "mAlI", "yapılabilir": "Ar", "anlatır": "Ar", "var": "ad", "müdür": "ad",
                    "Ankara'dır": "DIr", "mısınız": "soru"}
        for w, s in beklenen.items():
            with self.subTest(w):
                self.assertEqual(self.sinif(w), (s, True))

    def test_belirsizde_karar_yok(self):
        for w in ("kaldır", "değiştir", "insanlar", "gelir"):
            with self.subTest(w):
                self.assertFalse(self.sinif(w)[1])

    def test_dir_turu(self):
        self.assertEqual(ek.dir_turu("yıllardır"), ("sure", True))
        self.assertEqual(ek.dir_turu("müdür"), ("kok", True))
        self.assertEqual(ek.dir_turu("önemlidir"), ("kopula", True))
        self.assertEqual(ek.dir_turu("şunlardır"), ("kopula", True))
        self.assertEqual(ek.dir_turu("belirtir")[0], None)

    def test_ulac_ve_makta(self):
        self.assertEqual(ek.ulac_mi("yaparak"), (True, True))
        self.assertEqual(ek.ulac_mi("gerek")[0], False)
        self.assertEqual(ek.makta_mi("artırmakta", "ve"), (True, True))
        self.assertEqual(ek.makta_mi("bulmakta", "zorlanıyor"), (False, True))
        self.assertEqual(ek.makta_mi("ekmekte"), (False, True))


if __name__ == "__main__":
    unittest.main()


class IncelemeBulgulari(unittest.TestCase):
    """Codex incelemesinin (18.11.2026) bulduğu hatalar tekrar etmesin."""

    def kurallar(self, metin):
        from terzi.denetci import denetle
        return [b.kural for b in denetle(metin, yol="dar").bulgular]

    def test_kod_icinde_kural_yok(self):
        self.assertEqual(self.kurallar("İçinde `hızlı, ucuz ve temiz; genç, mutlu ve sakin; açık, kısa ve sade` yazıyor."), [])

    def test_bloklar_satir_satir(self):
        b = coz("Geldi.\n\nYarın sabah\nköye dönüyoruz.")
        self.assertEqual(len(b.cumleler), 2)
        b = coz("Gün bitti.\n## Yapay Zekâ Ve Gelecek")
        self.assertEqual([x.tur for x in b.bloklar], ["paragraf", "baslik"])

    def test_cumle_sinirlari(self):
        self.assertEqual(len(coz("“Notum 85.” Ayşe kâğıdı katladı.").cumleler), 2)
        self.assertEqual(len(coz("Şeker, un vb. Sonra yumurta ekleyin.").cumleler), 2)
        self.assertEqual(len(coz("Adresi https://ornek.org. Ertesi gün baktım.").cumleler), 2)
        self.assertEqual(coz("19. yüzyılda İstanbul büyüdü.").bloklar[0].tur, "paragraf")

    def test_ek_yanlis_alarmlari(self):
        self.assertNotIn("R001", self.kurallar("Tat damakta. Yara parmakta. Sorun üst basamakta."))
        self.assertNotIn("R001", self.kurallar("Önce ışığı söndür. Sonra çocuğu uyandır. En son ocağı söndür."))
        self.assertNotIn("R006", self.kurallar("Bugün Siverek'e gittik. Eski dostum Siverek'te yaşıyor. "
                                                "Yolda yağmur başladı. Otobüsten indim. Eve vardım."))
        self.assertNotIn("R002", self.kurallar(" ".join(["Yolu bulmakta zorlandım."] * 10)))

    def test_sade_buyuk_sapka(self):
        self.assertEqual(sade("RESMÎ"), "resmi")

    def test_uzun_metin_hizli(self):
        import time
        t0 = time.time()
        coz("Ali geldi. " * 3000)
        self.assertLess(time.time() - t0, 1.0)
