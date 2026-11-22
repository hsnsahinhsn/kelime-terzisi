import json
import unittest

from terzi import bilgi, duzeltici


class CozTest(unittest.TestCase):
    def test_bos_listeler_sorun_degil(self):
        r = bilgi.coz('Sonuç: {"eksik": [], "degisen": [], "eklenen": []}')
        self.assertFalse(r.sorun)
        self.assertEqual(r.hata, "")

    def test_sorun_ve_satirlar(self):
        r = bilgi.coz('{"eksik": [{"kaynakta": "14.00", "aciklama": "saat düştü"}], '
                      '"degisen": [{"kaynakta": "artış", "duzeltmede": "azalış", "aciklama": "yön"}], "eklenen": []}')
        self.assertTrue(r.sorun)
        self.assertEqual(len(r.satirlar()), 2)
        self.assertIn("'14.00'", r.satirlar()[0])

    def test_duz_metin_oge_sorun_sayilir(self):
        r = bilgi.coz('{"eksik": ["tarih düştü"], "degisen": [], "eklenen": []}')
        self.assertTrue(r.sorun)
        self.assertEqual(r.eksik, [{"aciklama": "tarih düştü"}])
        self.assertEqual(bilgi.coz('{"eksik": "yok", "degisen": [], "eklenen": []}').hata, "eksik liste değil")

    def test_bozuk_yanit_hata(self):
        self.assertEqual(bilgi.coz("bilmiyorum").hata, "JSON yok")
        self.assertTrue(bilgi.coz("{eksik: ]}").hata.startswith("JSON bozuk"))

    def test_yalin_denetim_uc_listeyi_de_ister(self):
        for yanit in ('{}', '{"eksik": [], "degisen": []}', '{"eksik": [], "degisen": [], "eklenen": null}'):
            with self.subTest(yanit=yanit):
                self.assertTrue(bilgi.denetle("Kaynak.", "Düzeltme.", lambda ist: yanit).hata)
        yanit = '{"eksik": [], "degisen": [], "eklenen": []}'
        self.assertEqual(bilgi.denetle("Kaynak.", "Düzeltme.", lambda ist: yanit), bilgi.Rapor())
        self.assertEqual(bilgi.coz("{}"), bilgi.Rapor())

    def test_istem_iki_metni_tasir(self):
        ist = bilgi.istem("Kaynak metin.", "Düzeltilmiş metin.")
        self.assertIn("KAYNAK:\nKaynak metin.", ist)
        self.assertTrue(ist.rstrip().endswith("Düzeltilmiş metin."))

    def test_envanter_istemleri_yazar_notunu_disarida_tutar(self):
        # Yazarın isteyene notu envantere girerse onarım notu metne geri ekliyordu (terzi-v13-o2t, 21.11.2026).
        for istem in (bilgi.envanter_istem, bilgi.tur_istem):
            self.assertIn(bilgi.YAZAR_NOTU, istem("Kaynak.", "Düzeltme."))


class EnvanterCozTest(unittest.TestCase):
    def test_gecerli_durumlar_ve_ekleme(self):
        yanit = json.dumps(dict(envanter=[dict(kaynakta="a", durum="AYNI"),
                                         dict(kaynakta="b", duzeltmede="c", durum="FarkLI"),
                                         dict(kaynakta="d", durum="YoK")], eklenen=[dict(duzeltmede="e")]))
        r = bilgi.envanter_coz(yanit)
        self.assertEqual(r.hata, "")
        self.assertEqual(r.eksik, [dict(kaynakta="d", aciklama="")])
        self.assertEqual(r.degisen, [dict(kaynakta="b", duzeltmede="c", aciklama="")])
        self.assertEqual(r.eklenen, [dict(duzeltmede="e", aciklama="")])
        self.assertEqual(bilgi.envanter_coz('{"envanter": [], "eklenen": []}'), bilgi.Rapor())

    def test_listeler_zorunlu(self):
        for yanit in (dict(eklenen=[]), dict(envanter=None, eklenen=[]), dict(envanter=[]),
                      dict(envanter=[], eklenen={}), dict(envanter=[], eklenen=None)):
            with self.subTest(yanit=yanit):
                self.assertTrue(bilgi.envanter_coz(json.dumps(yanit)).hata)

    def test_envanter_ogeleri_dogrulanir(self):
        for oge in ("metin", dict(durum="ayni"), dict(kaynakta=3, durum="ayni"), dict(kaynakta="a"),
                    dict(kaynakta="a", durum=None), dict(kaynakta="a", durum="bilinmiyor", tur="nezaket")):
            with self.subTest(oge=oge):
                yanit = json.dumps(dict(envanter=[dict(kaynakta="b", durum="yok"), oge], eklenen=[]))
                r = bilgi.envanter_coz(yanit, yalniz_bilgi=True)
                self.assertTrue(r.hata)
                self.assertFalse(r.sorun)

    def test_eklenen_ogeler_dogrulanir(self):
        for oge in ("metin", dict(tur="sus"), dict(duzeltmede=3)):
            with self.subTest(oge=oge):
                yanit = json.dumps(dict(envanter=[], eklenen=[oge]))
                self.assertTrue(bilgi.envanter_coz(yanit, yalniz_bilgi=True).hata)


class DonguTest(unittest.TestCase):
    metin = "Toplantı 14.00'te başlayacak. Herkesin katılması bekleniyor.\n"

    def test_bilgi_sorunu_ikinci_turu_tetikler(self):
        cagri = []

        def bm(ist):
            cagri.append(ist)
            return ('{"eksik": [{"kaynakta": "14.00", "aciklama": ""}], "degisen": [], "eklenen": []}'
                    if len(cagri) == 1 else '{"eksik": [], "degisen": [], "eklenen": []}')
        s = duzeltici.duzelt(self.metin, "eposta", lambda ist: "Toplantı başlayacak.", kip="kisa", taban=None,
                             bilgi_model=bm)
        self.assertEqual(s.turlar, 2)
        self.assertEqual(len(s.bilgi), 2)
        self.assertIn("Eksik bilgi", s.istemler[1])

    def test_bilgi_temizse_tek_tur(self):
        s = duzeltici.duzelt(self.metin, "eposta", lambda ist: self.metin, kip="kisa", taban=None,
                             bilgi_model=lambda ist: '{"eksik": [], "degisen": [], "eklenen": []}')
        self.assertEqual(s.turlar, 1)
        self.assertEqual(s.metinler, [self.metin.strip()])

    def test_bilgi_kipinde_iz_ikinci_turu_tetiklemez(self):
        iz = "Toplantı yarın – saat 14.00'te – başlayacak. Lütfen gelin – geç kalmayın.\n"
        s = duzeltici.duzelt(iz, "eposta", lambda ist: iz, kip="kisa", taban=None,
                             bilgi_model=lambda ist: '{"eksik": [], "degisen": [], "eklenen": []}')
        self.assertEqual(s.turlar, 1)
        self.assertEqual(duzeltici.duzelt(iz, "eposta", lambda ist: iz, kip="kisa", taban=None).turlar, 2)

    def test_cozulemeyen_denetim_bir_kez_yinelenir(self):
        cagri = []

        def bm(ist):
            cagri.append(ist)
            return "yanıt yok"
        s = duzeltici.duzelt(self.metin, "eposta", lambda ist: self.metin, kip="kisa", taban=None, bilgi_model=bm)
        self.assertEqual(len(cagri), 2)
        self.assertEqual(s.turlar, 1)
        self.assertTrue(s.bilgi[-1]["hata"])

    def test_bilgi_ikinci_turu_kaynaga_donmez(self):
        cagri = []

        def bm(ist):
            cagri.append(ist)
            return ('{"eksik": [{"kaynakta": "14.00", "aciklama": ""}], "degisen": [], "eklenen": []}'
                    if len(cagri) == 1 else '{"eksik": [], "degisen": [], "eklenen": []}')
        cikti = iter(["Toplantı başlayacak.", "Toplantı 14.00'te başlayacak."])
        s = duzeltici.duzelt(self.metin, "eposta", lambda ist: next(cikti), kip="kisa", taban=None, bilgi_model=bm)
        self.assertNotIn("kaynak metne dön", s.istemler[1])
        self.assertIn("söyleyişine dönme", s.istemler[1])
        self.assertEqual(s.metinler, ["Toplantı başlayacak.", "Toplantı 14.00'te başlayacak."])


class BulgusuzTest(unittest.TestCase):
    def test_bulgusuz_istemde_denetci_listesi_yok(self):
        metin = "Toplantı yarın – saat 14.00'te – başlayacak.\n"
        r = duzeltici.denetle(metin, "eposta")
        self.assertIn("Bir denetçi", duzeltici.istem(metin, "eposta", r, kip="kisa", taban=None))
        self.assertNotIn("Bir denetçi", duzeltici.istem(metin, "eposta", r, kip="kisa", taban=None, bulgu=False))


if __name__ == "__main__":
    unittest.main()
