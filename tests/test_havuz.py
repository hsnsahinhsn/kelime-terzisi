import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, call, patch
from urllib.error import HTTPError

from terzi import akis, havuz
from terzi.__main__ import main

IMZA = " 7.05, 2 Ocak 2021 (UTC)\n"
SOZLER = "Çınarın altında üç küçük kuş gördüm. Göl kıyısındaki taşlara konup su içtiler.".split()


def metin(sayi=80, bas="", son=""):
    return " ".join(bas.split() + (SOZLER * 20)[:sayi - len(bas.split()) - len(son.split())] + son.split())


def revizyon(baslik, zaman, icerik):
    return dict(title=baslik, revisions=[dict(timestamp=zaman, slots={"main": {"*": icerik}})])


class HavuzTest(unittest.TestCase):
    def setUp(self):
        self.kok = Path(self.enterContext(tempfile.TemporaryDirectory(dir=Path.cwd())))
        self.ham = self.kok / "ham"
        self.cikti = self.kok / "havuz"

    def ham_yaz(self, ad, icerik):
        yol = self.ham / ad
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(icerik, encoding="utf-8")

    def test_bol_imza_baslik_temizlik_ve_sira(self):
        vikimetin = ("== İlk ==\nAtılacak.\n== Son ==\n"
                    ": '''Merhaba'''  <!-- gizli\nnot --> <ref>not</ref><ref name='a'/> <i>bugün</i> "
                    "{{dış|{{iç}}}} [[Dosya:resim.png]] [[Kategori:Kuşlar]] [[Kullanıcı:Uydurma]] "
                    "[[Kuş|kuşları]] [[park]] [https://ornek.invalid gördüm] ''yine'' (mesaj) (katkılar)\n\n\n"
                    "# " + metin(40) + " --")
        temiz = "Merhaba bugün kuşları park gördüm yine \n\n" + metin(40)
        self.ham_yaz("danisma/a.txt", metin(42) + IMZA)
        self.ham_yaz("koy-cesmesi/z.txt", metin(41) + IMZA)
        self.ham_yaz("koy-cesmesi/a.txt", vikimetin + IMZA + metin(40) + IMZA.replace("7.05", "17:05") + metin())
        mesajlar = havuz.bol(self.ham)
        self.assertEqual(mesajlar, [
            dict(kaynak="koy-cesmesi", sayfa="a", yil=2021, kelime=46, metin=temiz),
            dict(kaynak="koy-cesmesi", sayfa="a", yil=2021, kelime=40, metin=metin(40)),
            dict(kaynak="koy-cesmesi", sayfa="z", yil=2021, kelime=41, metin=metin(41)),
            dict(kaynak="danisma", sayfa="a", yil=2021, kelime=42, metin=metin(42)),
        ])

    def test_bol_suzgecleri(self):
        elenenler = [metin() + IMZA.replace("2021", "2022"), metin(39) + IMZA, metin(221) + IMZA,
                     metin(49, "THE and") + IMZA, "bir uzak kedi " * 20 + IMZA]
        for iz in ("(WMF)", "message delivery", "Int:", "translate", "MediaWiki", "bot",
                   "https://ornek.invalid", "http://ornek.invalid", "www.ornek.invalid", "{{", "}}", "|", "==", "__"):
            elenenler.append(metin(80, son=iz) + IMZA)
        kalanlar = [metin(40), metin(50, "THE and"), metin(220), metin(80, son="robotlar")]
        self.ham_yaz("danisma/a.txt", "".join(elenenler) + "".join(t + IMZA for t in kalanlar))
        self.assertEqual([x["metin"] for x in havuz.bol(self.ham)], kalanlar)

    def test_havuz_suzgecleri(self):
        elenenler = [metin(49), metin(161), metin(80, "Bence", "?") + " ", metin(79),
                     "Ç " + "kedi " * 79, "Kedi " * 80]
        for iz in ('"a" "b"', "“a” “b”", "a\n\nb\n\nc\n\nd", "APTAL",
                   "imzasız", "tarafından eklenmiştir", "!!", "ÇĞİÖŞÜ"):
            elenenler.append(metin() + " " + iz)
        for t in elenenler:
            with self.subTest(son=t[-30:]):
                self.assertIsNone(havuz._sinif(dict(kaynak="koy-cesmesi", metin=t, kelime=len(t.split()))))

    def test_havuz_siniflari_ve_jsonl(self):
        gruplar = {
            "eposta": [("danisma", metin(50, ad, "?"))
                       for ad in ("Merhaba", "Selam", "Sayın", "Değerli", "Arkadaşlar", "Herkese")],
            "ajan": [("danisma", metin(50, "Bence", "?"))],
            "sosyal": [("koy-cesmesi", metin(160, ad))
                       for ad in ("Bence", "Ben de", "Katılıyorum", "Evet", "Hayır", "Bana göre", "Bu konuda")],
            "blog": [("koy-cesmesi", metin(80)), ("koy-cesmesi", "ÇÇÇ" + "a" * 97 + " 0" * 79)],
        }
        mesajlar, beklenen = [], {}
        for tur, grup in gruplar.items():
            satirlar = []
            for kaynak, t in grup:
                n = len(t.split())
                mesajlar.append(dict(kaynak=kaynak, sayfa="Köy", yil=2021, kelime=n, metin=t))
                satirlar.append(f'{{"kaynak": "{kaynak}", "sayfa": "Köy", "yil": 2021, "kelime": {n}, "metin": "{t}"}}\n')
            beklenen[tur] = "".join(satirlar).encode("utf-8")
        self.assertEqual(havuz.kur(mesajlar, self.cikti), {tur: len(v) for tur, v in gruplar.items()})
        self.assertEqual({yol.stem: yol.read_bytes() for yol in self.cikti.iterdir()}, beklenen)

    def test_arsivden_jsonl_ve_bosalan_havuz(self):
        t = ("Uzun süredir bahçedeki kuşların hangi ağaçlara konduğunu merak ediyordum. "
             "Dün sabah pencereyi açıp bir süre onları izledim. Önce çınara uğradılar, sonra gölün "
             "kıyısındaki söğüde geçtiler. Öğleye doğru ortalık sessizleşince aşağı indim. Çınarın "
             "dibinde birkaç küçük tüy buldum. Akşamüstü yağmur dindiğinde kuşlar yeniden geldi. "
             "Bu kez dalların arasında iki yavru gördüm.")
        self.ham_yaz("danisma/Kuşlar.txt", ": " + t.replace("çınara", "[[Çınar|çınara]]") + IMZA)
        bos = dict(eposta=0, ajan=0, sosyal=0, blog=0)
        self.assertEqual(havuz.kur(havuz.bol(self.ham), self.cikti), dict(bos, ajan=1))
        beklenen = ('{"kaynak": "danisma", "sayfa": "Kuşlar", "yil": 2021, "kelime": 50, "metin": "' + t + '"}\n')
        self.assertEqual((self.cikti / "ajan.jsonl").read_bytes(), beklenen.encode("utf-8"))
        self.assertEqual(havuz.kur([], self.cikti), bos)
        self.assertEqual({yol.stem: yol.read_bytes() for yol in self.cikti.iterdir()}, dict.fromkeys(bos, b""))

    def test_indir_sayfalama_gruplar_sabitleme_ve_devam(self):
        koy = [f"Vikipedi:Köy çeşmesi/Arşiv/2020/Konu {i:02}" for i in range(23)]
        masa = "Vikipedi:Danışma masası/Arşiv/Mayıs 2021"
        yeni = "2026-11-19T08:05:31Z"
        self.ham_yaz(f"koy-cesmesi/{koy[0].replace('/', '__')}.txt", "Önceden yazdım.")

        def liste(basliklar, **ek):
            return dict(query=dict(allpages=[dict(title=b) for b in basliklar]), **ek)

        def sayfalar(*sayfa, **ek):
            return dict(query=dict(pages={str(i): p for i, p in enumerate(sayfa, 1)}), **ek)

        devam = {"continue": "||", "rvcontinue": "sonraki sürüm"}
        api = Mock(side_effect=[
            liste(koy[:10], **{"continue": dict(apcontinue="sonraki", **{"continue": "-||"})}),
            liste(koy[10:] + ["Vikipedi:Köy çeşmesi/2022", "Vikipedi:Köy çeşmesi/Not"]),
            sayfalar(*(revizyon(b, havuz.SABIT, metin()) for b in koy[1:20])),
            sayfalar(revizyon(koy[20], yeni, "Yeni."), dict(title=koy[21]), dict(title=koy[22], missing=""),
                     **{"continue": devam}),
            sayfalar(dict(title=koy[20]), revizyon(koy[21], yeni, "Yeni.")),
            sayfalar(revizyon(koy[20], havuz.SABIT, "Eski.")), sayfalar(dict(title=koy[21])),
            liste([masa]), sayfalar(revizyon(masa, havuz.SABIT, "Danışma.")),
        ])
        with patch.object(havuz.time, "sleep") as bekle:
            havuz.indir(self.kok, api=api)
        listele = dict(action="query", list="allpages", apnamespace=4, aplimit=500)
        getir = dict(action="query", prop="revisions", rvprop="content|timestamp", rvslots="main")
        sabitle = dict(rvstart="2026-11-19T08:05:30Z", rvdir="older", rvlimit=1)
        self.assertEqual(api.call_args_list, [
            call(apprefix="Köy çeşmesi", **listele),
            call(apprefix="Köy çeşmesi", apcontinue="sonraki", **{"continue": "-||"}, **listele),
            call(titles="|".join(koy[1:20]), **getir), call(titles="|".join(koy[20:]), **getir),
            call(titles="|".join(koy[20:]), **getir, **devam),
            call(titles=koy[20], **getir, **sabitle), call(titles=koy[21], **getir, **sabitle),
            call(apprefix="Danışma masası/Arşiv", **listele), call(titles=masa, **getir),
        ])
        self.assertEqual(bekle.call_args_list, [call(2)] * 8)
        beklenen = {b.replace("/", "__") + ".txt": metin() for b in koy[1:20]}
        beklenen[koy[0].replace("/", "__") + ".txt"] = "Önceden yazdım."
        beklenen[koy[20].replace("/", "__") + ".txt"] = "Eski."
        self.assertEqual({p.name: p.read_text(encoding="utf-8") for p in (self.ham / "koy-cesmesi").iterdir()}, beklenen)
        self.assertEqual((self.ham / "danisma" / (masa.replace("/", "__") + ".txt")).read_bytes(), "Danışma.".encode())

    def test_indir_eksik_ve_gizli_surumu_bildirir(self):
        ad = "Vikipedi:Köy çeşmesi/2021"
        gizli = dict(title=ad, revisions=[dict(timestamp=havuz.SABIT, slots={"main": {"texthidden": ""}})])
        yeni = revizyon(ad, "2026-11-19T08:05:31Z", "Yeni.")
        for sayfalar in ([dict(title=ad)], [gizli], [yeni, gizli]):
            with self.subTest(sayfalar=sayfalar), patch.object(havuz.time, "sleep"):
                api = Mock(side_effect=[dict(query=dict(allpages=[dict(title=ad)])),
                                        *(dict(query=dict(pages={"1": p})) for p in sayfalar)])
                with self.assertRaisesRegex(RuntimeError, ad):
                    havuz.indir(self.kok, api=api)

    def test_sabitli_sorgu_devami_izlemez_ve_gizli_son_surumu_atlar(self):
        ad = "Vikipedi:Köy çeşmesi/2021"
        gizli_yeni = dict(title=ad, revisions=[dict(timestamp="2026-11-19T08:05:31Z", slots={"main": {"texthidden": ""}})])
        api = Mock(side_effect=[dict(query=dict(allpages=[dict(title=ad)])),
                                dict(query=dict(pages={"1": gizli_yeni})),
                                dict(query=dict(pages={"1": revizyon(ad, havuz.SABIT, "Eski.")}),
                                     **{"continue": {"rvcontinue": "daha eski", "continue": "||"}}),
                                dict(query=dict(allpages=[]))])
        with patch.object(havuz.time, "sleep"):
            havuz.indir(self.kok, api=api)
        self.assertEqual(api.call_count, 4)
        self.assertEqual((self.ham / "koy-cesmesi" / (ad.replace("/", "__") + ".txt")).read_text(encoding="utf-8"), "Eski.")

    def test_api_429_ve_kullanici_ajani(self):
        with patch.object(havuz.time, "sleep") as bekle, patch.object(havuz.urllib.request, "urlopen") as ac:
            hata = HTTPError("https://ornek.invalid", 429, "429", {}, None)
            ac.side_effect = [hata, hata, io.BytesIO(b'{"query": {}}')]
            self.assertEqual(havuz._api(action="query"), dict(query={}))
            istek = ac.call_args.args[0]
            self.assertEqual(istek.get_header("User-agent"), "kelime-terzisi (ornek havuzu indirme; dusuk hacim)")
            self.assertEqual(istek.full_url, "https://tr.wikipedia.org/w/api.php?action=query&format=json")
            self.assertEqual(bekle.call_args_list, [call(10), call(20)])

    def test_havuz_arama_sirasi(self):
        ayar = self.kok / "ayar"
        depo = self.kok / "veri" / "insan-gundelik" / "havuz"
        onbellek = self.kok / "kelime-terzisi" / "havuz"
        ortam = dict(XDG_CACHE_HOME=str(self.kok))
        with patch.object(akis, "PAKET", self.kok / "terzi"), patch.dict(os.environ, ortam, clear=True):
            self.assertIsNone(akis.gundelik_havuz())
            for yol in (onbellek, depo):
                yol.mkdir(parents=True)
                self.assertEqual(akis.gundelik_havuz(), yol)
                (yol / "ajan.jsonl").write_text(f'{{"metin": "{yol.parent.name}"}}\n', encoding="utf-8")
                self.assertEqual(akis.ornekler("Örnek", "ajan"), [yol.parent.name])
            with patch.dict(os.environ, KT_GUNDELIK_HAVUZ=str(ayar)):
                self.assertIsNone(akis.gundelik_havuz())
                self.assertEqual(akis.ornekler("Örnek", "ajan"), [])
                ayar.mkdir()
                self.assertEqual(akis.gundelik_havuz(), ayar)
            with patch.dict(os.environ, KT_GUNDELIK_HAVUZ=""):  # boş değer ayarlanmamış sayılır
                self.assertEqual(akis.gundelik_havuz(), depo)
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, "home", return_value=self.kok):
            self.assertEqual(havuz.varsayilan_kok(), self.kok / ".cache" / "kelime-terzisi")

    def test_komutlar(self):
        self.ham_yaz("danisma/a.txt", metin() + IMZA)
        with patch.object(havuz, "indir") as indir, redirect_stdout(io.StringIO()) as cikti:
            self.assertEqual(main(["havuz", "--kok", str(self.kok)]), 0)
        indir.assert_called_once_with(self.kok)
        self.assertIn("ajan 1", cikti.getvalue())
        self.assertIn("CC BY-SA 4.0", cikti.getvalue())
        self.assertIn("Claude'a gönderdiği isteme ekler", cikti.getvalue())
        for komut, ek, uyari in (("duzelt", [], True), ("istem", ["--v11"], True), ("istem", [], False)):
            with patch.object(akis, "gundelik_havuz", return_value=None), patch.object(akis, "duzelt",
                    return_value=akis.Sonuc("Göl kıyısı.", [])), patch("sys.stdin", io.StringIO("Göl kıyısı.")):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as hata:
                    self.assertEqual(main([komut, "-", "--tur", "blog"] + ek), 0)
            satirlar = hata.getvalue().splitlines()
            self.assertEqual(len(satirlar), int(uyari))
            if uyari:
                self.assertIn("python3 -m terzi havuz", satirlar[0])
