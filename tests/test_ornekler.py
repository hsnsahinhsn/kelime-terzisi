"""Pakete giren insan üslup örnekleri: biçim, uzunluk, kaynak satırı ve tür kapsamı."""
import json
import unittest
from pathlib import Path

from terzi import akis, yazim
from terzi.kural import TURLER

KLASOR = Path(akis.__file__).resolve().parent / "ornekler"
ORNEKLER = json.loads((KLASOR / "ornekler.json").read_text(encoding="utf-8"))
KAYNAK = (KLASOR / "KAYNAK.md").read_text(encoding="utf-8")


class OrnekDosyasi(unittest.TestCase):
    def test_turler_bilinen(self):
        self.assertLessEqual(set(ORNEKLER), TURLER)

    def test_her_ornek_kisa_ve_kaynakli(self):
        for tur, liste in ORNEKLER.items():
            for x in liste:
                with self.subTest(tur=tur, kaynak=x.get("kaynak")):
                    self.assertEqual(set(x), {"metin", "kaynak"})
                    self.assertTrue(x["metin"].strip())
                    self.assertLessEqual(len(x["metin"].split()), 140)
                    self.assertTrue(x["kaynak"].strip())
                    if tur != "anlati":  # öyküde konuşma çizgisi TDK kuralıdır
                        self.assertNotIn("—", x["metin"])

    def test_gundelik_disi_her_tur_ornekli(self):
        # Gündelik türler kullanıcının indirdiği havuzdan gelir; "genel" türün örneği yoktur.
        beklenen = TURLER - akis.GUNDELIK - {"genel"}
        for tur in sorted(beklenen):
            with self.subTest(tur=tur):
                self.assertGreaterEqual(len(ORNEKLER.get(tur, [])), 2)

    def test_kaynak_tablosu_ornek_sayisiyla_esit(self):
        satir = [s for s in KAYNAK.splitlines() if s.startswith("| ") and not s.startswith(("| Tür", "| ---"))]
        for tur, liste in ORNEKLER.items():
            with self.subTest(tur=tur):
                bu = [s for s in satir if s.startswith(f"| {tur} |")]
                self.assertEqual(len(bu), len(liste))
                kelime = sorted(int(s.rstrip(" |").rsplit("|", 1)[1]) for s in bu)
                self.assertEqual(kelime, sorted(len(x["metin"].split()) for x in liste))

    def test_ornek_secimi_rapor_ve_kurumsal(self):
        for tur in ("rapor", "kurumsal"):
            with self.subTest(tur=tur):
                orn = akis.ornekler("Toplantı özeti", tur)
                self.assertEqual(len(orn), 6)
                self.assertEqual(len(set(orn)), 6)
                self.assertLessEqual(set(orn), {x["metin"] for x in ORNEKLER[tur]})
                self.assertEqual(orn, akis.ornekler("Toplantı özeti", tur))
                self.assertEqual(akis.duzeltme_ornekleri("Toplantı özeti", tur), [])  # yalnız yazarken
                self.assertIn("Örnek 6:", yazim.yazim_istemi(tur, "Toplantı özeti"))
        self.assertEqual(akis.duzeltme_ornekleri("Bir not", "teknik"), akis.ornekler("Bir not", "teknik"))


if __name__ == "__main__":
    unittest.main()
