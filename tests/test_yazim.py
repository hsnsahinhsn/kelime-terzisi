"""Yazarken koruma istemi: insan örnekleri ve uydurma yasağı (python3 -m terzi yazim)."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from terzi import __main__ as cli, akis, yazim


class YazimTest(unittest.TestCase):
    def test_orneksiz_bos(self):
        self.assertEqual(yazim.istem([]), "")

    def test_ornekler_ve_kural_sirayla(self):
        metin = yazim.istem([" Birinci örnek. ", "İkinci örnek."])
        self.assertTrue(metin.startswith(yazim.GIRIS + yazim.ORNEK_GIRISI + "Örnek 1:\nBirinci örnek.\n\nÖrnek 2:\n"))
        self.assertTrue(metin.endswith("\n\n" + yazim.KILIT))

    def test_secim_konuya_ya_da_ture_bagli(self):
        with patch.object(akis, "ornekler", return_value=["Bir örnek."]) as orn:
            yazim.yazim_istemi("eposta", "  Toplantı notu  ")
            yazim.yazim_istemi("haber")
        self.assertEqual([c.args for c in orn.call_args_list], [("Toplantı notu", "eposta"), ("haber", "haber")])

    def _cli(self, *argv):
        cikti, hata = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(cikti), contextlib.redirect_stderr(hata):
            kod = cli.main(["yazim", *argv])
        return kod, cikti.getvalue(), hata.getvalue()

    def test_komut_istemi_yazar(self):
        with patch.object(akis, "ornekler", return_value=["Bir örnek."]):
            kod, cikti, hata = self._cli("--tur", "haber", "--konu", "Köprü açıldı")
        self.assertEqual((kod, hata), (0, ""))
        self.assertEqual(cikti, yazim.istem(["Bir örnek."]) + "\n")

    def test_komut_orneksiz_turde_uyarir(self):
        with patch.object(akis, "ornekler", return_value=[]):
            kod, cikti, hata = self._cli("--tur", "rapor")
        self.assertEqual((kod, cikti), (0, ""))
        self.assertIn("rapor türünde insan örneği yok", hata)

    def test_komut_havuzsuz_gundelikte_indirmeyi_soyler(self):
        with patch.object(akis, "ornekler", return_value=[]), patch.object(akis, "gundelik_havuz", return_value=None):
            kod, cikti, hata = self._cli("--tur", "blog")
        self.assertEqual((kod, cikti), (0, ""))
        self.assertIn("python3 -m terzi havuz", hata)

    def test_komut_yarim_havuzda_indirmeyi_soyler(self):
        with tempfile.TemporaryDirectory() as kok:
            with patch.object(akis, "ornekler", return_value=[]), \
                    patch.object(akis, "gundelik_havuz", return_value=Path(kok)):
                kod, cikti, hata = self._cli("--tur", "blog")
        self.assertEqual((kod, cikti), (0, ""))
        self.assertIn("python3 -m terzi havuz", hata)

    def test_komut_bozuk_utf8_de_durur(self):
        with patch.object(akis, "ornekler", side_effect=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "geçersiz")):
            kod, cikti, hata = self._cli("--tur", "blog")
        self.assertEqual((kod, cikti), (1, ""))
        self.assertIn("utf-8", hata)

    def test_komut_bozuk_havuzda_durur(self):
        with patch.object(akis, "ornekler", side_effect=akis.AkisHatasi("örnek satırı bozuk")):
            kod, cikti, hata = self._cli("--tur", "blog")
        self.assertEqual((kod, cikti), (1, ""))
        self.assertIn("örnek satırı bozuk", hata)


if __name__ == "__main__":
    unittest.main()
