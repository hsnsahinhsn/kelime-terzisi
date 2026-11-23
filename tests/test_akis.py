import hashlib
import io
import json
import random
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from terzi import akis, bilgi, duzeltici, model
from terzi.__main__ import main
from terzi.denetci import denetle

KAYNAK = "Toplantı salı günü saat üçte başlayacak."
TUR = "teknik"
TEMIZ = json.dumps(dict(eksik=[], degisen=[], eklenen=[]))
SORUN = json.dumps(dict(eksik=[dict(kaynakta="salı günü", aciklama="Gün eksik.")], degisen=[], eklenen=[]))


def okur_yaniti(yapay=(), **puanlar):
    return json.dumps(dict(insan_olasilik=50, dogal=3, yapay=list(yapay), gerekce="Ritim eşit.") | puanlar)


class AkisTest(unittest.TestCase):
    def setUp(self):
        self.orn = self.enterContext(patch.object(akis, "ornekler", return_value=["Bir insan örneği."]))
        self.modeller = Mock()
        self.yazar = self.modeller.yazar
        self.okur = self.modeller.okur
        self.denetci = self.modeller.denetci
        self.anlam = self.modeller.anlam
        self.yazar.return_value = KAYNAK
        self.okur.return_value = okur_yaniti()
        self.denetci.return_value = self.anlam.return_value = TEMIZ

    def duzelt(self, **secenek):
        return akis.duzelt(KAYNAK, TUR, self.yazar, self.okur, self.denetci, **secenek)

    def onarim_istemi(self, once):
        return duzeltici.bilgi_istem(KAYNAK, once, bilgi.coz(SORUN).satirlar(), TUR)

    def test_sira_modeller_ve_istemler(self):
        ilk = "Toplantı saat üçte başlayacak."
        onarilmis = "**Toplantı** salı günü saat üçte başlayacak."
        yeniden = "Saat üçte başlayacak toplantı."
        son = "Salı günü saat üçte toplanıyoruz."
        yapay = ["Toplantı", "salı günü", "başlayacak"]
        self.yazar.side_effect = [f" {ilk}\n", onarilmis, yeniden, f"\n{son}  "]
        self.denetci.side_effect = [SORUN, SORUN]
        self.okur.return_value = f"```json\n{okur_yaniti([' ', None, *yapay, 'dördüncü'])}\n```"

        sonuc = self.duzelt(anlam_model=self.anlam)

        self.orn.assert_called_once_with(KAYNAK, TUR)
        self.assertEqual(self.modeller.mock_calls, [
            call.yazar(duzeltici.istem(KAYNAK, TUR, denetle(KAYNAK, TUR), self.orn.return_value,
                                     kip="kisa", taban=None, bulgu=False, kilit=True)),
            call.denetci(bilgi.istem(KAYNAK, ilk)),
            call.yazar(self.onarim_istemi(ilk)),
            call.okur(akis.okur_istem(onarilmis)),
            call.yazar(akis.yeniden_istem(onarilmis, TUR, yapay, "Ritim eşit.")),
            call.denetci(bilgi.istem(KAYNAK, yeniden)),
            call.yazar(self.onarim_istemi(yeniden)),
            call.anlam(bilgi.siki_istem(KAYNAK, son)),
            call.anlam(bilgi.hedef_istem(KAYNAK, son)),
        ])
        self.assertEqual(sonuc.metin, son)
        self.assertEqual([x["adim"] for x in sonuc.adimlar], ["ilk_yazim", "bilgi", "okur", "bilgi", "anlam", "anlam"])
        self.assertTrue(sonuc.adimlar[1]["onarim"])
        self.assertTrue(sonuc.adimlar[3]["onarim"])

    def test_tek_kilit_ilk_yazimda_var_okurda_yok(self):
        # Tek kilit denemesi (21.11.2026): ilk yazım kilidi kalır, okur adımındaki kalkar.
        yapay = ["Toplantı", "başlayacak"]
        self.okur.return_value = okur_yaniti(yapay)
        sonuc = self.duzelt(anlam="yok", okur_kilit=False)
        ilk, yeniden = (c.args[0] for c in self.yazar.call_args_list)
        self.assertIn(duzeltici.ILK_KILIT, ilk)
        self.assertEqual(yeniden, akis.yeniden_istem(KAYNAK, TUR, yapay, "Ritim eşit.", kilit=False))
        self.assertNotIn(akis.KILIT, yeniden)
        self.assertNotIn("kilit", sonuc.adimlar[0])
        self.assertIs(sonuc.adimlar[2]["kilit"], False)

    def test_tekrar_kurali_yalniz_istenince_ilk_yazimda(self):
        # Tekrar denemesi (v1.4, 23.11.2026): kural yalnız ilk yazım istemine girer.
        sonuc = self.duzelt(anlam="yok", tekrar=True)
        self.assertIn(duzeltici.TEKRAR, self.yazar.call_args_list[0].args[0])
        self.assertTrue(all(duzeltici.TEKRAR not in c.args[0] for c in self.yazar.call_args_list[1:]))
        self.assertTrue(sonuc.adimlar[0]["tekrar"])
        self.yazar.reset_mock()
        sonuc = self.duzelt(anlam="yok")
        self.assertTrue(all(duzeltici.TEKRAR not in c.args[0] for c in self.yazar.call_args_list))
        self.assertNotIn("tekrar", sonuc.adimlar[0])

    def test_kilitli_ve_kilitsiz_okur_istemi(self):
        yapay = ["Toplantı"]
        for secenek, beklenen in ((dict(), True), (dict(kilit=False), False), (dict(kilit=False, okur_kilit=True), True)):
            with self.subTest(secenek=secenek):
                self.yazar.reset_mock()
                self.okur.return_value = okur_yaniti(yapay)
                self.duzelt(anlam="yok", **secenek)
                yeniden = self.yazar.call_args_list[1].args[0]
                self.assertEqual(akis.KILIT in yeniden, beklenen)

    def test_iki_okur_turu(self):
        # Tarama (21.11.2026): ikinci okur turu bir önceki turun metnini okur, sonra bilgi denetimi.
        self.okur.return_value = okur_yaniti(["Toplantı"])
        self.yazar.side_effect = ["ilk", "birinci tur", "ikinci tur"]
        sonuc = self.duzelt(anlam="yok", okur_kilit=False, okur_turu=2)
        self.assertEqual(self.okur.call_args_list, [call(akis.okur_istem("ilk")), call(akis.okur_istem("birinci tur"))])
        self.assertEqual(self.yazar.call_args_list[2], call(akis.yeniden_istem("birinci tur", TUR, ["Toplantı"],
                                                                               "Ritim eşit.", kilit=False)))
        self.assertEqual(sonuc.metin, "ikinci tur")
        self.assertEqual([x["adim"] for x in sonuc.adimlar], ["ilk_yazim", "bilgi", "okur", "bilgi", "okur", "bilgi"])
        with self.assertRaises(ValueError):
            self.duzelt(okur_turu=0)

    def test_okur_kaynak_yeniden_yazima_kaynagi_verir(self):
        # Tarama (21.11.2026, terzi-v13i-o2s): okurun yeniden yazımı anlam için kaynağı görür; ilk yazım değişmez.
        self.okur.return_value = okur_yaniti(["Toplantı"])
        self.yazar.side_effect = ["ilk", "birinci tur", "ikinci tur"]
        sonuc = self.duzelt(anlam="yok", okur_kilit=False, okur_turu=2, okur_kaynak=True)
        for i, once in ((1, "ilk"), (2, "birinci tur")):
            istem = self.yazar.call_args_list[i].args[0]
            self.assertEqual(istem, akis.yeniden_istem(once, TUR, ["Toplantı"], "Ritim eşit.", kilit=False, kaynak=KAYNAK))
            self.assertTrue(istem.endswith(akis.OKUR_KAYNAK + KAYNAK.strip()))
        self.assertNotIn(akis.OKUR_KAYNAK, self.yazar.call_args_list[0].args[0])
        self.assertTrue(all(x.get("kaynak") for x in sonuc.adimlar if x["adim"] == "okur"))
        self.assertEqual(akis.yeniden_istem("m", TUR, ["a"], "g"), akis.yeniden_istem("m", TUR, ["a"], "g", kaynak=None))

    def test_tur_anlam_kipi_yalniz_bilgi_turlerini_onarir(self):
        yanit = json.dumps({"envanter": [
            {"kaynakta": "Tarihi bildirin.", "duzeltmede": "Değişirse bildirin.", "durum": "farkli", "tur": "kosul",
             "aciklama": "koşul eklendi"},
            {"kaynakta": "Dört gözle bekliyorum.", "duzeltmede": "", "durum": "yok", "tur": "duygu", "aciklama": "düştü"},
            {"kaynakta": "Saat üç.", "duzeltmede": "Saat üç.", "durum": "ayni", "tur": "", "aciklama": ""}],
            "eklenen": []})
        bos = json.dumps({"envanter": [], "eklenen": []})
        self.anlam.side_effect = [yanit, bos]
        onarilmis = KAYNAK + " Onarıldı."
        self.yazar.side_effect = [KAYNAK, onarilmis]
        sonuc = self.duzelt(anlam="tur", anlam_model=self.anlam)
        self.assertEqual(self.anlam.call_args_list, [call(bilgi.tur_istem(KAYNAK, KAYNAK)),
                                                     call(bilgi.tur_istem(KAYNAK, onarilmis))])
        onarim = self.yazar.call_args_list[1].args[0]
        self.assertIn("Değişirse bildirin.", onarim)
        self.assertNotIn("Dört gözle", onarim)
        self.assertEqual(sonuc.metin, onarilmis)
        self.assertEqual(sonuc.adimlar[-1]["kip"], "tur")
        self.assertEqual(sonuc.adimlar[-1]["onarim"], 1)

    def test_envanter_coz(self):
        r = bilgi.envanter_coz('{"envanter": [{"kaynakta": "a", "durum": "yok", "tur": "nezaket"}], "eklenen": '
                               '[{"duzeltmede": "e", "tur": "ayrinti", "aciklama": "y"}]}')
        self.assertEqual((len(r.eksik), len(r.eklenen)), (1, 1))
        r = bilgi.envanter_coz('{"envanter": [{"kaynakta": "a", "durum": "yok", "tur": "nezaket"}], "eklenen": []}',
                               yalniz_bilgi=True)
        self.assertFalse(r.sorun)
        self.assertEqual(r.hata, "")
        self.assertTrue(bilgi.envanter_coz("yanıt yok").hata)
        self.assertTrue(bilgi.envanter_coz('{"eksik": []}').hata)

    def test_bos_yapay_yeniden_yazmaz_ve_anlam_yok(self):
        sonuc = self.duzelt(anlam="yok", anlam_model=self.anlam)
        self.assertEqual(self.yazar.call_count, 1)
        self.assertEqual(self.denetci.call_args_list, [call(bilgi.istem(KAYNAK, KAYNAK))] * 2)
        self.anlam.assert_not_called()
        self.assertFalse(sonuc.adimlar[2]["yeniden_yazim"])
        self.assertEqual(len(sonuc.adimlar), 4)

    def test_bilgi_bozuk_yaniti_yineler_ve_ikinci_hatada_durur(self):
        self.denetci.side_effect = ["{}", TEMIZ, "{}", "{}"]
        with self.assertRaisesRegex(akis.AkisHatasi, "bilgi denetimi iki kez"):
            self.duzelt(anlam="yok")
        self.assertEqual(self.denetci.call_args_list, [call(bilgi.istem(KAYNAK, KAYNAK))] * 4)
        self.okur.assert_called_once()

    def test_okur_alinti_siniri_istemde_ve_kayitta(self):
        self.assertEqual(akis.okur_istem("Metin."), akis.okur_istem("Metin.", 3))
        self.assertIn("en çok 5 yeri", akis.okur_istem("Metin.", 5))
        yapay = [f"yer{i}" for i in range(7)]
        self.okur.return_value = okur_yaniti(yapay)
        self.yazar.side_effect = [KAYNAK, "yeni"]
        sonuc = self.duzelt(anlam="yok", okur_alinti=5)
        self.assertEqual(self.okur.call_args_list, [call(akis.okur_istem(KAYNAK, 5))])
        self.assertEqual(sonuc.adimlar[2]["yapay"], yapay[:5])
        self.assertEqual(self.yazar.call_args_list[1], call(akis.yeniden_istem(KAYNAK, TUR, yapay[:5], "Ritim eşit.")))
        for kotu in (0, 5.0, True):
            with self.subTest(kotu=kotu), self.assertRaises(ValueError):
                self.duzelt(okur_alinti=kotu)

    def test_okur_bozuk_yaniti_yineler(self):
        self.okur.side_effect = ["{bozuk}", okur_yaniti(insan_olasilik=100, dogal=1)]
        self.duzelt(anlam="yok")
        self.assertEqual(self.okur.call_args_list, [call(akis.okur_istem(KAYNAK))] * 2)

    def test_okur_yapay_listesi_olmadan_durur(self):
        self.okur.side_effect = ['{"insan_olasilik": 50, "dogal": 3}',
                                 '{"insan_olasilik": 50, "dogal": 3, "yapay": null}']
        with self.assertRaisesRegex(akis.AkisHatasi, "okur yanıtı iki kez.*alıntıları liste değil"):
            self.duzelt(anlam="yok")
        self.assertEqual(self.okur.call_args_list, [call(akis.okur_istem(KAYNAK))] * 2)
        self.denetci.assert_called_once()

    def test_okur_gecersiz_puanlarda_durur(self):
        self.okur.side_effect = [okur_yaniti(insan_olasilik=101), okur_yaniti(dogal=0)]
        with self.assertRaisesRegex(akis.AkisHatasi, "okur yanıtı iki kez"):
            self.duzelt()
        self.assertEqual(self.okur.call_count, 2)
        self.denetci.assert_called_once()

    def test_anlam_her_onarimi_denetler_ve_ikide_durur(self):
        bir = "Salı günü saat üçte toplantı var."
        iki = "Salı saat üçte toplantı var."
        self.yazar.side_effect = [KAYNAK, bir, iki]
        self.anlam.side_effect = [SORUN, SORUN, SORUN]
        sonuc = self.duzelt(anlam_model=self.anlam, anlam="siki")
        self.assertEqual(sonuc.metin, iki)
        self.assertEqual(sonuc.adimlar[-1]["onarim"], 2)
        self.assertEqual(self.anlam.call_args_list, [call(bilgi.siki_istem(KAYNAK, m)) for m in (KAYNAK, bir, iki)])
        self.assertEqual(self.yazar.call_args_list[1:], [call(self.onarim_istemi(m)) for m in (KAYNAK, bir)])

    def test_siki_hedef_iki_donguyu_sirayla_calistirir(self):
        bir = "Salı günü saat üçte toplantı var."
        self.yazar.side_effect = [KAYNAK, bir]
        self.anlam.side_effect = [TEMIZ, SORUN, TEMIZ]
        sonuc = self.duzelt(anlam_model=self.anlam, anlam="siki-hedef")
        self.assertEqual(sonuc.metin, bir)
        self.assertEqual(self.anlam.call_args_list, [call(bilgi.siki_istem(KAYNAK, KAYNAK)),
                                                     call(bilgi.hedef_istem(KAYNAK, KAYNAK)),
                                                     call(bilgi.hedef_istem(KAYNAK, bir))])
        self.assertEqual([(x["kip"], x["onarim"]) for x in sonuc.adimlar[-2:]], [("siki", 0), ("hedef", 1)])

    def test_anlam_temizlenince_durur_ve_varsayilan_model_yazar(self):
        yeni = "Salı günü saat üçte toplanıyoruz."
        self.yazar.side_effect = [KAYNAK, "{}", SORUN, yeni, TEMIZ, TEMIZ]
        sonuc = self.duzelt()
        self.assertEqual(sonuc.metin, yeni)
        self.assertEqual(akis.ANLAM_VARSAYILAN, "siki-hedef")
        self.assertEqual([(x["kip"], x["onarim"]) for x in sonuc.adimlar[-2:]], [("siki", 1), ("hedef", 0)])
        self.assertEqual(self.yazar.call_args_list[1:], [
            call(bilgi.siki_istem(KAYNAK, KAYNAK)), call(bilgi.siki_istem(KAYNAK, KAYNAK)),
            call(self.onarim_istemi(KAYNAK)), call(bilgi.siki_istem(KAYNAK, yeni)), call(bilgi.hedef_istem(KAYNAK, yeni)),
        ])

    def test_anlam_iki_hata_sonra_durur(self):
        self.anlam.return_value = "{}"
        with self.assertRaisesRegex(akis.AkisHatasi, "anlam denetimi iki kez"):
            self.duzelt(anlam_model=self.anlam)
        self.assertEqual(self.anlam.call_count, 2)
        self.yazar.assert_called_once()

    def test_envanter_iki_hata_sonra_durur(self):
        self.anlam.return_value = '{"envanter": []}'
        with self.assertRaisesRegex(akis.AkisHatasi, "anlam denetimi iki kez"):
            self.duzelt(anlam_model=self.anlam, anlam="envanter")
        self.assertEqual(self.anlam.call_args_list, [call(bilgi.envanter_istem(KAYNAK, KAYNAK))] * 2)
        self.yazar.assert_called_once()

    def test_anlam_yaridan_kisa_onarimi_reddeder(self):
        self.anlam.return_value = SORUN
        self.yazar.side_effect = [KAYNAK, "Salı günü."]
        with self.assertRaisesRegex(akis.AkisHatasi, "çok kısa"):
            self.duzelt(anlam_model=self.anlam)
        self.anlam.assert_called_once()

    def test_bos_yazim_hata_verir(self):
        self.yazar.return_value = " \n "
        with self.assertRaisesRegex(akis.AkisHatasi, "boş metin"):
            self.duzelt()
        self.denetci.assert_not_called()


class IstemTest(unittest.TestCase):
    def test_ornek_havuzlari(self):
        with tempfile.TemporaryDirectory() as dizin:
            kok = Path(dizin)
            havuz = [f"Örnek {i}" for i in range(10)]
            (kok / "ajan.jsonl").write_text("\n".join(json.dumps(dict(metin=m)) for m in havuz), encoding="utf-8")
            (kok / "blog.jsonl").touch()
            (kok / "ornekler").mkdir()
            (kok / "ornekler" / "ornekler.json").write_text(
                json.dumps({TUR: [dict(metin=m) for m in havuz[:2]]}), encoding="utf-8")
            with patch.dict(akis.os.environ, {"KT_GUNDELIK_HAVUZ": dizin}), patch.object(akis, "PAKET", kok):
                tohum = hashlib.sha256(KAYNAK.encode("utf-8")).hexdigest()
                beklenen = random.Random(tohum).sample(havuz, 6)
                self.assertEqual(akis.ornekler(KAYNAK, "ajan"), beklenen)
                self.assertEqual(akis.ornekler(KAYNAK, "ajan"), beklenen)
                self.assertCountEqual(akis.ornekler(KAYNAK, TUR), havuz[:2])
                for tur in ("blog", "eposta", "genel"):
                    self.assertEqual(akis.ornekler(KAYNAK, tur), [])


class ModelTest(unittest.TestCase):
    def test_claude_komut_ortam_ve_json(self):
        env = dict(PATH="/bin", CLAUDECODE="1", CLAUDE_EFFORT="high", claude_x="1", ANTHROPIC_TEST="1", anthropic_x="1")
        yanit = dict(type="result", subtype="success", is_error=False, stop_reason="end_turn", result=" Metin. ")

        def calistir(komut, **ayarlar):
            self.assertEqual(komut, [
                "claude", "-p", "--output-format", "json", "--setting-sources", "", "--tools", "",
                "--strict-mcp-config", "--no-session-persistence", "--effort", "xhigh", "--model", "claude-opus-5-5",
            ])
            bos = Path(ayarlar.pop("cwd"))
            self.assertEqual(list(bos.iterdir()), [])
            ortam = dict(PATH="/bin", CLAUDE_CODE_DISABLE_CLAUDE_MDS="1", CLAUDE_CODE_DISABLE_AUTO_MEMORY="1")
            self.assertEqual(ayarlar, dict(input="İstem.", env=ortam, capture_output=True,
                                           text=True, timeout=900))
            return SimpleNamespace(returncode=0, stdout=json.dumps(yanit))

        with patch.dict(model.os.environ, env, clear=True), patch.object(model.subprocess, "run", side_effect=calistir) as kos:
            cagir = model.claude(model.OPUS)
            self.assertEqual(cagir("İstem."), "Metin.")
            self.assertFalse(Path(kos.call_args.kwargs["cwd"]).exists())
            kos.side_effect = None
            for ham in ("bozuk", "[]", json.dumps(dict(yanit, stop_reason="max_tokens"))):
                kos.return_value = SimpleNamespace(returncode=0, stdout=ham)
                with self.subTest(ham=ham), self.assertRaises(model.ModelHatasi):
                    cagir("İstem.")


class KomutTest(unittest.TestCase):
    def calis(self, *arguman):
        with patch("sys.stdin", io.StringIO(KAYNAK)), redirect_stdout(io.StringIO()) as cikti:
            self.assertEqual(main(list(arguman)), 0)
        return cikti.getvalue()

    def test_duzelt_metin_ve_json(self):
        opus = Mock(side_effect=[KAYNAK, TEMIZ, TEMIZ, KAYNAK])  # yazım, sıkı denetim, hedefli denetim; ikinci çağrı yazım
        sonnet = Mock(side_effect=[TEMIZ, okur_yaniti(), TEMIZ] * 2)
        # Bu test temel akışın komut satırı kaydını sınar; ürün akışının ayarları ayrı testte (URUN_AKISI).
        with patch.object(model, "claude", side_effect=[opus, sonnet] * 2) as fabrika, \
                patch.dict(akis.URUN_AKISI, {}, clear=True):
            sonuc = json.loads(self.calis("duzelt", "-", "--tur", TUR, "--json"))
            self.assertEqual(self.calis("duzelt", "-", "--tur", TUR, "--anlam", "yok"), KAYNAK + "\n")
        self.assertEqual(fabrika.call_args_list, [call("claude-opus-5-5"), call("claude-sonnet-5-5")] * 2)
        self.assertEqual(sonuc["metin"], KAYNAK)
        self.assertEqual((sonuc["modeller"]["yazar"], sonuc["modeller"]["okur"], sonuc["effort"]),
                         ("claude-opus-5-5", "claude-sonnet-5-5", "xhigh"))
        self.assertEqual([x["kip"] for x in sonuc["adimlar"][-2:]], list(akis.ANLAM_DONGULERI[akis.ANLAM_VARSAYILAN]))

    def test_istem_v11_ilk_istemle_ayni(self):
        orn = ["Bir insan örneği."]
        with patch.object(akis, "ornekler", return_value=orn), patch.object(model, "claude") as fabrika:
            cikti = self.calis("istem", "-", "--tur", TUR, "--v11")
        self.assertEqual(cikti, duzeltici.istem(KAYNAK, TUR, denetle(KAYNAK, TUR), orn,
                                               kip="kisa", taban=None, bulgu=False, kilit=True))
        self.assertIn(duzeltici.ILK_KILIT, cikti)
        fabrika.assert_not_called()

    def test_duzelt_urun_akisini_kullanir(self):
        self.assertEqual(akis.URUN_AKISI, dict(okur_kilit=False, son_okur=1, yama_turu=3))
        with patch.object(model, "claude"), patch.object(akis, "duzelt", side_effect=RuntimeError("dur")) as dz, \
                patch("sys.stdin", io.StringIO(KAYNAK)), self.assertRaises(RuntimeError):
            main(["duzelt", "-", "--tur", TUR])
        self.assertEqual({k: dz.call_args.kwargs[k] for k in akis.URUN_AKISI}, akis.URUN_AKISI)
        self.assertEqual(dz.call_args.kwargs["anlam"], akis.ANLAM_VARSAYILAN)

    def test_duzelt_model_hatasini_standart_hataya_yazar(self):
        yazar = Mock(side_effect=model.ModelHatasi("çağrı başarısız"))
        with patch.object(model, "claude", return_value=yazar), patch("sys.stdin", io.StringIO(KAYNAK)):
            with redirect_stdout(io.StringIO()) as cikti, redirect_stderr(io.StringIO()) as hata:
                self.assertEqual(main(["duzelt", "-", "--tur", TUR, "--json"]), 1)
        self.assertEqual(cikti.getvalue(), "")
        self.assertIn("çağrı başarısız", hata.getvalue())


class BosGirdiTest(unittest.TestCase):
    def test_bos_metin_model_cagirmaz(self):
        cagri = []
        model = lambda istem: cagri.append(istem) or ""
        with self.assertRaises(akis.AkisHatasi):
            akis.duzelt("  \n ", "haber", model, model, model)
        self.assertEqual(cagri, [])


class YazarNotuTest(unittest.TestCase):
    # Örnekler sınav taslaklarından (inceleme 23.11.2026, docs/v1.4-claude-taslak.md).
    GOVDE = "Yürüyüşten döndüm.\n\nTaşı masaya koydum."

    def test_ayiraclı_notlar_ayrilir(self):
        for not_ in ("Metin konu satırıyla birlikte yaklaşık 128 kelime. Taşın rengini ve diğer ayrıntıları "
                     "yürüyüşüne göre değiştirebilirsin.",
                     "*(Başlık hariç yaklaşık 255 kelime.)*",
                     "Metin başlıklar dahil 187 kelimedir ve yalnız verdiğiniz bilgilere dayanır.",
                     "*Not: Bugün 22 Kasım 2026. Metne yıl eklemedim. Yayımlamadan önce tarihleri kontrol edin.*",
                     "Not: Conta değişiminin saati verilmediği için çizelgede böyle yazdım."):
            with self.subTest(not_=not_):
                self.assertEqual(akis.yazar_notu_ayir(f"{self.GOVDE}\n\n---\n\n{not_}\n"), (self.GOVDE, not_))

    def test_ayiracsiz_not_paragrafi_siki_kuralla_ayrilir(self):
        not_ = "*Not: Doğrulayamadığım bilgileri uydurmamak için köşeli parantezle boş bıraktım.*"
        self.assertEqual(akis.yazar_notu_ayir(f"{self.GOVDE}\n\n{not_}"), (self.GOVDE, not_))

    def test_icerik_notlari_kalir(self):
        for metin in (f"{self.GOVDE}\n\nNot: Nisan öncesinde gelen istekler bu raporun kapsamı dışındadır.",
                      f"{self.GOVDE}\n\n**Not:** Dosyaları yeniden dışa aktarmanız gerekir.",
                      f"{self.GOVDE}\n\nNot: Faturayı da ekledim.",
                      f"{self.GOVDE}\n\nNot: İsterseniz toplantıyı salıya alabiliriz.",
                      f"{self.GOVDE}\n\nNot: Başvurular 500 kelimeyi geçmemelidir.",
                      f"{self.GOVDE}\n\nNot: Köşeli parantez içindeki parametreler isteğe bağlıdır.",
                      f"{self.GOVDE}\n\nNot: İsterseniz formu değiştirebilirsiniz.",
                      f"{self.GOVDE}\n\n---\n\nNot: Faturayı da ekledim.",
                      f"{self.GOVDE}\n\n---\n\nYayımlamadan önce kurul onayı alınır.",
                      f"{self.GOVDE}\n\nSonuç\n---\nMetin yaklaşık 100 kelime ama bu bölüm içerik.",
                      f"{self.GOVDE}\n\n---\n\nMetin yaklaşık 128 kelime.\n\nAyrıca kargo salı günü çıkacak.",
                      "\n\nNot: Doğrulayamadığım bilgileri uydurmadım.",
                      f"{self.GOVDE}\n\n---\n\nAyşe Yılmaz\nSatın Alma",
                      f"---\n\nMetin yaklaşık 128 kelime.",
                      "Tek paragraf, yaklaşık 128 kelime yazdım.",
                      # ikinci Codex incelemesi (23.11.2026): koşul sayım değildir, nottaki yeni sayı ve tarih kalır
                      f"{self.GOVDE}\n\nNot: Başvuru metni en az 500 kelime olmalıdır.",
                      f"{self.GOVDE}\n\nNot: Metin en fazla 300 kelime olmalı.",
                      f"{self.GOVDE}\n\nNot: Metin yaklaşık 170 kelime. Ürün 5 Aralık'ta kargoya verilecek.",
                      f"{self.GOVDE}\n\n---\n\nMetin yaklaşık 170 kelime. Toplantı salı günü yapılacak.",
                      # üçüncü Codex incelemesi: nottaki her cümle yazarın yorumu olmalı; "cuma" "cumartesi" değildir
                      f"{self.GOVDE}\n\nNot: Metin yaklaşık 170 kelime. Kargo ücretsizdir.",
                      f"{self.GOVDE}\n\nNot: Metin yaklaşık 170 kelime. Bugün 5 paket gönderilecek.",
                      f"Ödeme cumartesi günü yapılır.\n\nNot: Metin yaklaşık 170 kelime. Ödeme cuma günü de yapılabilir.",
                      f"{self.GOVDE}\n\nNot: Metin yaklaşık 170 kelime. Faturayı da ekledim.",
                      f"{self.GOVDE}\n\nNot: Metin yaklaşık 170 kelime. Siparişi ücretsiz iade edebilirsiniz.",
                      f"{self.GOVDE}\n\nNot: Metin yaklaşık 170 kelime. Ayrıntılı bilgi için bizi arayabilirsiniz.",
                      # bugünün tarihi verilmeden tarih yorumu içerik sayılır
                      f"{self.GOVDE}\n\nNot: Metin yaklaşık 170 kelime. Son başvuru tarihi geçti."):
            with self.subTest(metin=metin):
                self.assertEqual(akis.yazar_notu_ayir(metin), (metin, ""))

    def test_satir_sonu_buyuk_harf_ve_cekimler(self):
        self.assertEqual(akis.yazar_notu_ayir(f"{self.GOVDE}\r\n\r\n---\r\n\r\nMETİN YAKLAŞIK 128 KELİME.\r\n"),
                         (self.GOVDE, "METİN YAKLAŞIK 128 KELİME."))
        for not_ in ("Tarih belirtmedim, verdiğiniz bilgide yoktu.", "Daha kısa bir metin isterseniz kısaltırım.",
                     "Metni güncel haber olarak yayımlayacaksanız rakamları teyit edin."):
            with self.subTest(not_=not_):
                self.assertEqual(akis.yazar_notu_ayir(f"{self.GOVDE}\n\n---\n\n{not_}")[1], not_)

    def test_notun_kendi_tarihi_ve_sayilari_yeni_bilgi_degil(self):
        govde = "Toplantı 7 Ekim'de, ikincisi 4 Ekim'de."
        for not_ in ("*Not: Bugün 22 Kasım 2026. Metindeki 7 Ekim ve 4 Ekim tarihleri geçmiş. Metne yıl eklemedim.*",
                     # sınav 3 S016: bugünün tarihi verilince metindeki tarihleri yorumlayan cümle de nottur
                     "*Not: Bugün 22 Kasım 2026. Bu yılın 7 Ekim ve 4 Ekim tarihleri geçmiş durumda. Metne yıl eklemedim. "
                     "Yayımlamadan önce tarihleri kontrol edin.*",
                     "Metin yaklaşık 170 kelime. Verdiğin bilgilerle 190'a kadar uzatmak yeni bilgi eklemeyi gerektirirdi, "
                     "o yüzden bıraktım. İstersen havanın nasıl olduğunu sen anlat, ben de bunu 190'a tamamlayayım."):
            with self.subTest(not_=not_):
                self.assertEqual(akis.yazar_notu_ayir(f"{govde}\n\n---\n\n{not_}"), (govde, not_))

    def test_uzun_blok_not_sayilmaz(self):
        uzun = "Bu bölümde verdiğiniz sayılar var. " + "Ölçüm sürdü. " * 60
        metin = f"{self.GOVDE}\n\n---\n\n{uzun}"
        self.assertEqual(akis.yazar_notu_ayir(metin), (metin, ""))

    def test_duzelt_notu_modele_gostermez_ve_ayri_verir(self):
        cagri = []
        temiz = json.dumps(dict(eksik=[], degisen=[], eklenen=[]))
        def model_(istem):
            cagri.append(istem)
            return okur_yaniti() if "insan_olasilik" in istem else (temiz if "KAYNAK" in istem else self.GOVDE)
        not_ = "Metin yaklaşık 128 kelime. Yalnızca verdiğiniz bilgileri kullandım."
        with patch.object(akis, "ornekler", return_value=[]):
            sonuc = akis.duzelt(f"{self.GOVDE}\n\n---\n{not_}", "eposta", model_, model_, model_, anlam="yok")
        self.assertEqual(sonuc.yazar_notu, not_)
        self.assertEqual(sonuc.adimlar[0], dict(adim="yazar_notu", ayrildi=not_))
        self.assertTrue(cagri)
        self.assertFalse(any("128 kelime" in istem for istem in cagri))

    def test_anlam_dongulerine_ve_yamaya_notsuz_kaynak_gider(self):
        temiz = json.dumps(dict(eksik=[], degisen=[], eklenen=[]))
        model_ = Mock(side_effect=lambda istem: okur_yaniti() if "insan_olasilik" in istem else
                      (temiz if "KAYNAK" in istem or "DÜZELT" in istem.upper() else self.GOVDE))
        not_ = "Metin yaklaşık 128 kelime."
        with patch.object(akis, "ornekler", return_value=[]), patch.object(akis, "_denetle", wraps=akis._denetle) as den, \
                patch.object(akis.dongu, "calistir", return_value=(self.GOVDE, [])) as dongu:
            sonuc = akis.duzelt(f"{self.GOVDE}\n\n---\n\n{not_}", "eposta", model_, model_, model_, yama_turu=1)
        self.assertEqual(sonuc.yazar_notu, not_)
        self.assertTrue(den.call_args_list)
        self.assertTrue(all(c.args[0] == self.GOVDE for c in den.call_args_list))
        self.assertEqual(dongu.call_args.args[0], self.GOVDE)

    def test_komut_json_notu_verir(self):
        sonuc = akis.Sonuc("Düzeltilmiş.", [dict(adim="yazar_notu", ayrildi="Metin 128 kelime.")], "Metin 128 kelime.")
        with patch.object(model, "claude"), patch.object(akis, "duzelt", return_value=sonuc), \
                patch("sys.stdin", io.StringIO(KAYNAK)), redirect_stdout(io.StringIO()) as cikti, \
                redirect_stderr(io.StringIO()) as hata:
            self.assertEqual(main(["duzelt", "-", "--tur", TUR, "--json"]), 0)
        self.assertEqual(json.loads(cikti.getvalue())["yazar_notu"], "Metin 128 kelime.")
        self.assertEqual(hata.getvalue(), "")

    def test_anlam_komutu_kaynaktaki_notu_saymaz(self):
        with tempfile.TemporaryDirectory() as d:
            k, s_ = Path(d, "k.md"), Path(d, "s.md")
            k.write_text(f"{self.GOVDE}\n\n---\n\nMetin yaklaşık 128 kelime.\n", encoding="utf-8")
            s_.write_text(self.GOVDE + "\n", encoding="utf-8")
            with redirect_stdout(io.StringIO()) as cikti, redirect_stderr(io.StringIO()) as hata:
                self.assertEqual(main(["anlam", str(k), str(s_)]), 0)
        self.assertEqual(cikti.getvalue(), "")
        self.assertIn("128 kelime", hata.getvalue())

    def test_komut_notu_standart_hataya_yazar(self):
        sonuc = akis.Sonuc("Düzeltilmiş.", [], "Metin 128 kelime.")
        with patch.object(model, "claude"), patch.object(akis, "duzelt", return_value=sonuc), \
                patch("sys.stdin", io.StringIO(KAYNAK)), redirect_stdout(io.StringIO()) as cikti, \
                redirect_stderr(io.StringIO()) as hata:
            self.assertEqual(main(["duzelt", "-", "--tur", TUR]), 0)
        self.assertEqual(cikti.getvalue(), "Düzeltilmiş.\n")
        self.assertIn("Metin 128 kelime.", hata.getvalue())
