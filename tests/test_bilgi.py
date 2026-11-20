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

    def test_istem_iki_metni_tasir(self):
        ist = bilgi.istem("Kaynak metin.", "Düzeltilmiş metin.")
        self.assertIn("KAYNAK:\nKaynak metin.", ist)
        self.assertTrue(ist.rstrip().endswith("Düzeltilmiş metin."))


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
