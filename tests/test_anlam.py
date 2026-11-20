import json, subprocess, sys, tempfile, unittest
from pathlib import Path

from terzi.anlam import Fark, karsilastir

class AnlamTest(unittest.TestCase):
    def farklar(self, tur, kaynak, sonuc):
        return [f for f in karsilastir(kaynak, sonuc) if f.tur == tur]

    def degerler(self, tur, kaynak, sonuc):
        return [(f.kaynakta, f.sonucta) for f in self.farklar(tur, kaynak, sonuc)]

    def test_bu_yuzden_sayi_degil(self):
        self.assertEqual(self.farklar("sayi", "Bu yüzden program yavaş açılır.", "Program bu nedenle yavaş açılır."), [])
        self.assertEqual(self.degerler("sayi", "Yüzden fazla kişi geldi.", "Birçok kişi geldi."), [("100", "")])

    def test_kesme_isareti_alintiyi_bozmaz(self):
        self.assertEqual(self.farklar("alinti", '"Ramazan’da pahalıydı." dedi.', '"Ramazan\'da pahalıydı." dedi.'), [])

    def test_ayni_metin(self):
        metin = 'TBMM, Ankara’da “Yaklaşık iki yıl önce yüzde 38,4 arttı.” dedi.'
        self.assertEqual(karsilastir(metin, metin), [])
        self.assertEqual(karsilastir("", ""), [])

    def test_sayi_bicimleri(self):
        for kaynak, sonuc in (
            ("oran %38,4", "oran yüzde 38,4"), ("oran %25", "oran YÜZDE yirmi beş"), ("oran yüzde bir", "oran %1"),
            ("ücret 1.250,50", "ücret 1250,5"), ("saat 14.30", "saat 14:30"), ("tarih 8.1.2026", "tarih 08.01.2026"),
            ("dönem 2024-2026", "dönem 2024 ile 2026"), ("iki yüz otuz beş", "235"), ("bir kitap", "kitap"),
            ("bir milyar iki milyon üç bin bir", "1.002.003.001"),
        ):
            self.assertEqual(self.farklar("sayi", kaynak, sonuc), [], kaynak)

    def test_sayi_farki(self):
        fark, = self.farklar("sayi", "su", "beş litre su")
        self.assertEqual((fark.duzey, fark.kaynakta, fark.sonucta), ("guclu", "", "5"))
        self.assertEqual(self.degerler("sayi", "5 ve 5 litre", "5 litre"), [("5", "")])
        for kaynak, sonuc in (("%25", "25"), ("-5", "5"), ("14:30", "1430"), ("18.11.2026", "18112026")):
            self.assertEqual(len(self.farklar("sayi", kaynak, sonuc)), 2, kaynak)

    def test_sayi_baglam(self):
        fark, = karsilastir("süresi yüzde 38,4 arttı", "hızı yüzde 38,4 arttı")
        self.assertEqual((fark.tur, fark.duzey, fark.kaynakta, fark.sonucta), ("sayi_baglam", "zayif", "süresi", "hızı"))
        self.assertEqual(karsilastir("KÂR 5, HIZ 5", "HIZ 5, KAR 5"), [])
        self.assertEqual(karsilastir("KÂR 5, HIZ 4", "KAR 5, HIZ 4"), [])
        self.assertEqual(karsilastir("sayı 5’ten 6’ya çıktı", "sayı 5'den 6'ya çıktı"), [])

    def test_ad(self):
        self.assertEqual(self.farklar("ad", "Ankara'da", "Ankara’ya"), [])
        self.assertEqual(self.degerler("ad", "Ankara", "İzmir"), [("ankara", ""), ("", "izmir")])
        self.assertEqual(self.degerler("ad", "TBMM toplandı. Sonra dağıldı.", "Meclis toplandı. Ardından dağıldı."), [("tbmm", "")])
        self.assertIn(("", "izmir"), self.degerler("ad", "Bugün Ankara kalabalık.", "Bugün İzmir kalabalık."))

    def test_olumsuz(self):
        for kaynak in (
            "gelmiyor", "bakmıyor", "durmuyor", "gülmüyor", "gelmedi", "bakmadı", "gelmezsin", "bakmaz",
            "gelmemiş", "bakmamış", "gelmeyecek", "bakmayacak", "gelmemeli", "bakmamalı", "gelmeden",
            "bakmadan", "gelmeyen", "bakmayan", "değil", "yok", "hiç", "hiçbir", "asla", "ne o ne bu",
            "değilsiniz", "gelmiyorlardı", "gelmeyeceğini",
        ):
            fark, = self.farklar("olumsuz", kaynak, "geldi")
            self.assertEqual((fark.duzey, fark.kaynakta, fark.sonucta), ("guclu", "1", "0"), kaynak)
        self.assertEqual(self.farklar("olumsuz", "Az kaldı.", "Az kaldı."), [])
        self.assertEqual(self.farklar("olumsuz", "Az biraz kaz yaz mezmur namaz elmadan damadan.", ""), [])

    def test_yon(self):
        self.assertTrue(self.farklar("yon", "arttı", "azaldı"))
        self.assertTrue(self.farklar("yon", "Arttı. Azaldı.", "Azaldı. Arttı."))
        self.assertTrue(self.farklar("yon", "daha fazla", ""))
        self.assertEqual(self.farklar("yon", "artık düşük olduğu düşünülüyor", ""), [])

    def test_ihtiyat(self):
        for kaynak in (
            "olabilir", "yapabilecek", "gelebileceğini", "muhtemelen", "belki", "galiba", "sanki", "görünüyor",
            "yaklaşık", "civarında", "neredeyse", "tahminen", "iddia", "öne sürüldü", "yapıldığı düşünülüyor",
        ):
            fark, = karsilastir(kaynak, "olur")
            self.assertEqual((fark.tur, fark.duzey, fark.kaynakta, fark.sonucta), ("ihtiyat", "zayif", "1", "0"), kaynak)

    def test_alinti(self):
        for sol, sag in (('"', '"'), ('“', '”'), ('«', '»')):
            kaynak = f'Uzman {sol}Kâr aynı.{sag} dedi.'
            fark, = self.farklar("alinti", kaynak, kaynak.replace("Kâr", "Kar"))
            self.assertEqual((fark.duzey, fark.kaynakta), ("guclu", "Kâr aynı."), sol)
        self.assertEqual(self.farklar("alinti", '«Aynen.»', '“Aynen.”'), [])

    def test_kod_ve_url(self):
        self.assertEqual(karsilastir('Sonuç ``"TBMM 5" `x` olamaz`` ve [rapor](https://örnek.test/2026).',
                                     'Sonuç `6 arttı` ve [rapor](https://örnek.test/2027).'), [])

    def test_rakamla_basamak(self):
        self.assertEqual(self.degerler("sayi", "2 milyon 3 bin lira", "3 milyon 2 bin lira"), [("2003000", ""), ("", "3002000")])
        self.assertEqual(self.farklar("sayi", "2,5 milyon", "2.500.000"), [])

    def test_sayi_durum_ekleri(self):
        for kaynak, sonuc in (("yüzde yirmi beşe", "%25"), ("yirmi dörde", "24"), ("otuzu", "30"), ("bine", "1000"), ("üçte", "3")):
            self.assertEqual(self.farklar("sayi", kaynak, sonuc), [], kaynak)

    def test_saatten_sonra_virgul(self):
        self.assertEqual(self.degerler("sayi", "14.30, istasyonda", "14.03, istasyonda"), [("14:30", ""), ("", "14:03")])

    def test_olumsuz_gereklilik_kisi_ekleri(self):
        for soz in ("yapmamalıyız", "yapmamalısınız", "yapmamalılar", "yapmamalıyım"):
            self.assertEqual(len(self.farklar("olumsuz", soz, "yapmalı")), 1, soz)

    def test_unvan_ve_bas_harf(self):
        for on in ("Dr.", "Prof.", "Doç.", "Av.", "Sn.", "Op.", "Uzm.", "Yrd.", "A."):
            self.assertEqual(self.degerler("ad", f"Hekim {on} Ayşe konuştu", f"Hekim {on} Ece konuştu"), [("ayşe", ""), ("", "ece")], on)

    def test_yon_simdiki_zaman(self):
        for soz, yon in (("yavaşlıyor", "Azalış"), ("genişliyor", "Artış"), ("azalıyor", "Azalış"), ("artıyor", "Artış"), ("büyüyor", "Artış")):
            self.assertTrue(self.farklar("yon", soz, "sürüyor")[0].ayrinti.startswith(yon), soz)

    def test_buyuk_ve_buyumek(self):
        self.assertEqual(self.farklar("yon", "büyük ve büyüğe", "iri"), [])
        for soz in ("büyüdü", "büyüyor", "büyümesi"):
            self.assertTrue(self.farklar("yon", soz, "iri"), soz)

    def test_kod_paragraf_siniri(self):
        self.assertTrue(self.farklar("sayi", "` 5\n\n7 `", "` 6\n\n7 `"))
        self.assertEqual(self.farklar("sayi", "`5\n7`", "`6\n7`"), [])

    def test_tek_sozcuklu_ad_karsilastirmasi(self):
        self.assertEqual(self.farklar("ad", "Evet.", "Evet, tamam."), [])
        self.assertEqual(self.farklar("ad", "Evet, tamam.", "Evet."), [])

    def test_komedi_olumsuz_degil(self):
        self.assertEqual(self.farklar("olumsuz", "komedi komediler trajikomedi", "oyunlar"), [])

    def test_soru_ve_olumsuz_ne(self):
        self.assertEqual(self.farklar("olumsuz", "Dün ne aldın, ne ödedin?", "Dün alışveriş yaptın mı?"), [])
        self.assertTrue(self.farklar("olumsuz", "Ne Ayşe ne Ece konuştu.", "Ayşe konuştu."))

    def test_iddia_ekleri(self):
        for soz in ("iddiasına göre", "iddia etti", "iddiaya göre"):
            self.assertEqual(len(self.farklar("ihtiyat", soz, "kesin")), 1, soz)

    def test_cli(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as klasor:
            kaynak, sonuc = (Path(klasor) / ad for ad in ("kaynak", "sonuc"))
            kaynak.write_text("olabilir", encoding="utf-8")
            komut = [sys.executable, "-m", "terzi.anlam", str(kaynak), str(sonuc)]
            sonuc.write_text("olur", encoding="utf-8")
            c = subprocess.run(komut, capture_output=True, text=True)
            self.assertEqual((c.returncode, len(c.stdout.splitlines()), c.stderr), (0, 1, ""))
            self.assertIn("zayif ihtiyat", c.stdout)
            sonuc.write_text("olur ve 5", encoding="utf-8")
            c = subprocess.run(komut + ["--json"], capture_output=True, text=True)
            self.assertEqual((c.returncode, c.stderr), (1, ""))
            self.assertEqual([Fark(**f) for f in json.loads(c.stdout)], karsilastir("olabilir", "olur ve 5"))


class IkinciInceleme(unittest.TestCase):
    """İkinci Codex incelemesinden (18.11.2026) Claude'un düzelttikleri."""

    def turler(self, a, b):
        from terzi.anlam import karsilastir
        return {f.tur for f in karsilastir(a, b) if f.duzey == "guclu"}

    def test_art_arda_yon_degil(self):
        self.assertNotIn("yon", self.turler("Yazarlar art arda konuştu.", "Yazarlar sırayla konuştu."))

    def test_firmadan_olumsuz_degil(self):
        self.assertNotIn("olumsuz", self.turler("Ödemeyi firmadan aldık.", "Ödemeyi şirketten aldık."))

    def test_geriliyor(self):
        self.assertIn("yon", self.turler("Satışlar geriliyor.", "Satışlar sabit."))
