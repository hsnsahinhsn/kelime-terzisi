import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from terzi import duzeltici
from terzi.__main__ import main
from terzi.denetci import denetle


class IstemTest(unittest.TestCase):
    def istem(self, tur):
        metin = "Bu bir deneme metnidir. Sonuç olarak her şey yolunda gitmektedir.\n"
        return duzeltici.istem(metin, tur, denetle(metin, tur))

    def test_kisa_istem_turu(self):
        ist = self.istem("eposta")
        self.assertIn("yüzde 85'inden kısa olmasın", ist)
        self.assertIn("Bir denetçi şu yerleri buldu", ist)
        self.assertNotIn(duzeltici.kart(), ist)
        self.assertNotIn(duzeltici.GENEL_IZ, ist)

    def test_sabit_tur_uzunlugu_ve_duzeni_korur(self):
        ist = self.istem("hukuk")
        self.assertIn("yüzde 95 ile 105", ist)
        self.assertIn(duzeltici.kart(), ist)
        self.assertIn(duzeltici.DUZEN_SIKI, ist)

    def test_haber_kisalmaz_ama_serbest_kurulur(self):
        ist = self.istem("haber")
        self.assertIn("yüzde 95 ile 105", ist)
        self.assertIn(duzeltici.DUZEN_SERBEST, ist)


    def test_komut_satiri_istemi(self):
        with tempfile.TemporaryDirectory() as d:
            yol = Path(d) / "m.txt"
            yol.write_text("Umarım bu e-posta sizi iyi bulur. Toplantı 14.00'te.\n", encoding="utf-8")
            cikti = io.StringIO()
            with contextlib.redirect_stdout(cikti):
                self.assertEqual(main(["istem", str(yol), "--tur", "eposta"]), 0)
        self.assertIn("Bir denetçi şu yerleri buldu", cikti.getvalue())
        self.assertTrue(cikti.getvalue().rstrip().endswith("Toplantı 14.00'te."))


if __name__ == "__main__":
    unittest.main()
