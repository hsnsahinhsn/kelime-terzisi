import json
import unittest
from unittest.mock import Mock, call, patch

from terzi import akis, dongu

KAYNAK = "Toplantı salı günü saat üçte başlayacak. Gelemeyen bize yazsın."
METIN = "Toplantı salı üçte. Gelemeyen yazsın.\n"
TEMIZ = json.dumps(dict(eksik=[], degisen=[], eklenen=[]))


def yama(*parcalar, atla=()):
    return json.dumps(dict(atlananlar=[dict(sorun=n, neden="aynı", alinti="x") for n in atla],
                           yamalar=[dict(sorun=n, eski=e, yeni=y) for n, e, y in parcalar]), ensure_ascii=False)


class DonguTest(unittest.TestCase):
    def test_istemler_ve_ornekler(self):
        blok = dongu.ornek_blogu()
        self.assertTrue(blok.startswith("MAJOR changes a strict checker found in other texts (edit | source):\nERR MAJOR | "))
        self.assertEqual(blok.count("\nERR MAJOR | "), 16)
        self.assertEqual(blok.count("\nERR MINOR | "), 8)
        ist = dongu.denetim_istemi(f"\n{KAYNAK}\n", METIN)
        self.assertIn(blok, ist)
        self.assertTrue(ist.endswith(f"SOURCE:\n{KAYNAK}\n\nEDIT:\n{METIN.strip()}"))
        y = dongu.yama_istemi("eposta", [("salı üçte", "salı günü saat üçte")], ["Bir örnek.\n"], KAYNAK, METIN)
        self.assertIn("1. Yeniden yazılmışta: «salı üçte». Kaynakta: «salı günü saat üçte». Sorun:", y)
        self.assertIn("Örnek 1:\nBir örnek.\n\nKaynak metin:", y)
        self.assertIn('{"atlananlar": [{"sorun": 2', y)
        self.assertIn("(Bu tür için örnek yok.)", dongu.yama_istemi("rapor", [("a", "b")], [], KAYNAK, METIN))

    def test_bulgular(self):
        self.assertEqual(dongu.bulgular("NONE"), [])
        self.assertEqual(dongu.bulgular("ERR MAJOR | “salı üçte” | salı günü\n- ERR MINOR | `a` | b"),
                         [("MAJOR", "salı üçte", "salı günü"), ("MINOR", "a", "b")])

    def test_yarim_satir_sonrakini_yutmaz_ve_duz_yazi_temiz_sayilmaz(self):
        self.assertEqual(dongu.bulgular("ERR MAJOR | a |\nERR MINOR | b | c"), [("MINOR", "b", "c")])
        self.assertEqual(dongu.denetle(Mock(side_effect=["Hiç sorun görmedim.", "NONE"]), KAYNAK, METIN), [])
        with self.assertRaises(dongu.DonguHatasi):
            dongu.denetle(Mock(side_effect=["Sorun yok.", "Gerçekten yok."]), KAYNAK, METIN)

    def test_gecersiz_numara_uygulanmaz_eksik_bulgu_yinelenir(self):
        ilk = yama((99, "Gelemeyen", "Katılamayan"))
        ikinci = yama((99, "Gelemeyen", "Katılamayan"), (1, "salı üçte", "salı günü üçte"))
        cagir = Mock(side_effect=["ERR MAJOR | salı üçte | salı günü", ilk, ikinci])
        metin, turlar = dongu.calistir(KAYNAK, METIN, "eposta", cagir, [], tur_sayisi=1)
        self.assertEqual(metin, "Toplantı salı günü üçte. Gelemeyen yazsın.\n")
        self.assertEqual(turlar[0]["hesap"], dict(gecersiz=1, eksik=[]))
        cagir = Mock(side_effect=["ERR MAJOR | salı üçte | salı günü", yama(), yama()])
        metin, turlar = dongu.calistir(KAYNAK, METIN, "eposta", cagir, [], tur_sayisi=1)
        self.assertEqual((metin, turlar[0]["hesap"]), (METIN, dict(gecersiz=0, eksik=[1])))

    def test_ortusen_gecis_iki_kez_sayilir(self):
        metin, uyg, atl = dongu.yama_uygula("ha ha ha", [dict(eski="ha ha", yeni="x")])
        self.assertEqual((metin, uyg, atl[0]["neden"]), ("ha ha ha", [], "metinde 2 kez"))

    def test_uc_tur_yalniz_agir_yamanir(self):
        cagir = Mock(side_effect=[
            "ERR MAJOR | salı üçte | salı günü saat üçte\nERR MINOR | yazsın | bize yazsın",
            yama((1, "salı üçte", "salı günü saat üçte")),
            "NONE",
            "ERR MINOR | x | y",
        ])
        metin, turlar = dongu.calistir(KAYNAK, METIN, "eposta", cagir, ["Örnek."])
        self.assertEqual(metin, "Toplantı salı günü saat üçte. Gelemeyen yazsın.\n")
        self.assertEqual(cagir.call_count, 4)
        self.assertEqual(cagir.call_args_list[1], call(dongu.yama_istemi(
            "eposta", [("salı üçte", "salı günü saat üçte")], ["Örnek."], KAYNAK, METIN)))
        self.assertEqual(cagir.call_args_list[2], call(dongu.denetim_istemi(KAYNAK, metin)))
        self.assertEqual([(t["agir"], t["uygulanan"]) for t in turlar], [(1, 1), (0, 0), (0, 0)])
        self.assertEqual(turlar[0]["atla_gerekce"], [])

    def test_atlanan_ve_bozuk_json(self):
        cagir = Mock(side_effect=["ERR MAJOR | salı | salı günü\nERR MAJOR | yazsın | bize yazsın", "bozuk",
                                  yama((2, "yazsın", "bize yazsın"), atla=(1,))])
        metin, turlar = dongu.calistir(KAYNAK, METIN, "eposta", cagir, [], tur_sayisi=1)
        self.assertEqual(metin, "Toplantı salı üçte. Gelemeyen bize yazsın.\n")
        self.assertEqual([x["sorun"] for x in turlar[0]["atla_gerekce"]], [1])
        with self.assertRaises(ValueError):
            dongu.calistir(KAYNAK, METIN, "eposta", Mock(side_effect=["ERR MAJOR | a | b", "x", "y"]), [], tur_sayisi=1)

    def test_cok_kisalan_yama_durur(self):
        cagir = Mock(side_effect=["ERR MAJOR | Toplantı salı üçte. Gelemeyen yazsın. | x", yama((1, "Toplantı salı üçte. Gelemeyen yazsın.", "Tamam."))])
        with self.assertRaises(dongu.DonguHatasi):
            dongu.calistir(KAYNAK, "Toplantı salı üçte. Gelemeyen yazsın.\n", "eposta", cagir, [], tur_sayisi=1)


class AkisDonguTest(unittest.TestCase):
    def test_son_okur_ve_yama_dongusu_sirasi(self):
        self.enterContext(patch.object(akis, "ornekler", return_value=["Bir insan örneği."]))
        yazar, okur, denetci = Mock(), Mock(), Mock()
        okur.return_value = json.dumps(dict(insan_olasilik=50, dogal=3, yapay=["Toplantı"], gerekce="Ritim eşit."))
        denetci.return_value = TEMIZ
        yazar.side_effect = ["ilk", "birinci tur", "son tur", "NONE", "NONE"]
        sonuc = akis.duzelt(KAYNAK, "eposta", yazar, okur, denetci, anlam="yok", okur_kilit=False, son_okur=1,
                            son_okur_kaynak=True, yama_turu=2)
        self.assertEqual(sonuc.metin, "son tur")
        self.assertEqual(yazar.call_args_list[2], call(akis.yeniden_istem("birinci tur", "eposta", ["Toplantı"], "Ritim eşit.",
                                                                          kilit=False, kaynak=KAYNAK)))
        self.assertEqual(yazar.call_args_list[3], call(dongu.denetim_istemi(KAYNAK, "son tur")))
        self.assertEqual([x["adim"] for x in sonuc.adimlar], ["ilk_yazim", "bilgi", "okur", "bilgi", "okur", "bilgi", "yama_dongusu"])
        self.assertTrue(sonuc.adimlar[4]["son"] and sonuc.adimlar[4]["kaynak"])
        self.assertEqual(len(sonuc.adimlar[-1]["turlar"]), 2)
        for kotu in (dict(son_okur=-1), dict(yama_turu=1.5)):
            with self.assertRaises(ValueError):
                akis.duzelt(KAYNAK, "eposta", yazar, okur, denetci, **kotu)

    def test_son_okur_yapay_yoksa_bilgi_denetimi_yok(self):
        self.enterContext(patch.object(akis, "ornekler", return_value=[]))
        yazar, okur, denetci = Mock(return_value="ilk"), Mock(), Mock(return_value=TEMIZ)
        okur.side_effect = [json.dumps(dict(insan_olasilik=50, dogal=3, yapay=["x"], gerekce="g")),
                            json.dumps(dict(insan_olasilik=80, dogal=5, yapay=[], gerekce="g"))]
        sonuc = akis.duzelt(KAYNAK, "eposta", yazar, okur, denetci, anlam="yok", son_okur=1)
        self.assertEqual([x["adim"] for x in sonuc.adimlar], ["ilk_yazim", "bilgi", "okur", "bilgi", "okur"])


if __name__ == "__main__":
    unittest.main()
