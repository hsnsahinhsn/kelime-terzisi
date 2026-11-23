"""Ölçülen v1.1 düzeltme akışı. Model çağrıları istem alır ve metin döner."""
import hashlib
import json
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path

from . import bilgi, denetci, dongu, duzeltici, havuz, yazar_notu

# Kilitli v1.1 sınavı (20.11.2026, 75 metin, aynı kör sınıflandırma): ağır değişiklikli görev yaklaşık 29 -> 16;
# doğallık iki hakem ortalamasında yaklaşık -1,3 (yalının yine yaklaşık 4 puan önünde).
ANLAM_VARSAYILAN = "siki-hedef"
ANLAM_KIPLERI = ("olgu", "siki", "siki-hedef", "envanter", "tur", "yok")
# Komut satırının akışı: okur adımında kilit yok, kaynaksız bir son okur turu, üç turluk Claude anlam döngüsü.
# Görülmemiş 75 görevde yalından %28,2 daha doğal [+4,83, +11,41 puan]; iki kör GPT anlam denetiminde ağır bulgu
# 11, yalın 39.
URUN_AKISI = dict(okur_kilit=False, son_okur=1, yama_turu=3)
# Her kip sırayla çalışan denetim ve onarım döngüleridir (bilgi.ISTEMLER anahtarları). hedef: sıkı denetimin
# kaçırdığı istek ve koşul, kapsam, eklenen ayrıntı farkları (bilgi.hedef_istem).
# envanter, tur: kaynağın bilgi envanteri ve madde madde eşleme (bilgi.envanter_istem, 21.11.2026 taraması); tur
# yalnız bilgi türlerini onarır.
ANLAM_DONGULERI = {"olgu": ("olgu",), "siki": ("siki",), "siki-hedef": ("siki", "hedef"), "envanter": ("envanter",),
                   "tur": ("tur",)}
GUNDELIK = set(havuz.TURLER)
PAKET = Path(__file__).resolve().parent


class AkisHatasi(RuntimeError):
    """Düzeltme akışı tamamlanamadı."""


@dataclass
class Sonuc:
    metin: str
    adimlar: list[dict]
    yazar_notu: str = ""


# Taslağın sonundaki yazar notu düzeltmeden önce ayrılır (terzi/yazar_notu.py, inceleme 23.11.2026).
yazar_notu_ayir = yazar_notu.ayir


def gundelik_havuz():
    """Gündelik örnekler için ilk bulunan havuz klasörünü döndür."""
    ayar = os.getenv("KT_GUNDELIK_HAVUZ")
    if ayar:  # açıkça verilen havuz: yoksa başka havuza düşülmez
        return Path(ayar) if Path(ayar).is_dir() else None
    depo = PAKET.parent / "veri" / "insan-gundelik" / "havuz"
    if depo.is_dir():
        return depo
    onbellek = havuz.varsayilan_kok() / "havuz"
    return onbellek if onbellek.is_dir() else None


def ornekler(metin, tur):
    """Aynı türden en çok altı insan örneği seç. Seçim metne bağlıdır."""
    try:
        if tur in GUNDELIK:
            kok = gundelik_havuz()
            if kok is None:
                return []
            yol = kok / f"{tur}.jsonl"
            havuz = []
            with yol.open(encoding="utf-8") as dosya:
                for no, s in enumerate(dosya, 1):
                    if not s.strip():
                        continue
                    try:
                        m = json.loads(s)["metin"]
                    except (ValueError, KeyError, TypeError) as e:
                        raise AkisHatasi(f"{yol}:{no}: örnek satırı bozuk ({e})") from e
                    if not isinstance(m, str) or not m.strip():
                        raise AkisHatasi(f"{yol}:{no}: örnek metni boş")
                    havuz.append(m)
        else:
            yol = PAKET / "ornekler" / "ornekler.json"
            havuz = [x["metin"] for x in json.loads(yol.read_text(encoding="utf-8")).get(tur, [])]
    except FileNotFoundError:
        return []
    tohum = hashlib.sha256(metin.encode("utf-8")).hexdigest()
    return random.Random(tohum).sample(havuz, min(6, len(havuz)))


# Rapor ve kurumsal örnekleri yalnız yazarken kullanılır (48 taslakta ölçüldü):
# düzelticinin ilk yazımında doğallık -1,17 [-3,08, +0,84] (rapor -2,00), yazarken +0,38 ve hafif bilgi hatası 8'den 2'ye.
YALNIZ_YAZIM = frozenset({"rapor", "kurumsal"})


def duzeltme_ornekleri(metin, tur):
    """Düzelticinin ilk yazımına giden örnekler: yalnız yazarken kullanılan türlerde örnek yok."""
    return [] if tur in YALNIZ_YAZIM else ornekler(metin, tur)


def ilk_istem(metin, tur, orn, kilit=True, tekrar=False):
    # Anlam kilidi (v1.3, 20.11.2026, olcum/ilkkilit_olc.sh, 45 taslak): kör Codex denetiminde anlam kayması bulguları
    # 53'ten 26'ya, ağırlar 4'ten 2'ye indi; doğallık +0,40 [-1,47, +2,24] (GPT hakemi), yani düşmedi.
    return duzeltici.istem(metin, tur, denetci.denetle(metin, tur), orn, kip="kisa", taban=None, bulgu=False,
                           kilit=kilit, tekrar=tekrar)


# Okura giden metin ve istem ölçümdeki olcum.hakem ve olcum.hakem_istem ile aynı kalır.
SAPKASIZ = str.maketrans("âîûÂÎÛ", "aiuAİU")
BITISIK = ((r"([İi])şbirliğ", r"\1ş birliğ"), (r"\b([Yy])urt(içi|dışı)", r"\1urt \2"), (r"\b([BbHh][ie]r)şey", r"\1 şey"),
           (r"\b([Oo]n)(bir|iki|üç|dört|dörd|beş|altı|yedi|sekiz|dokuz)", r"\1 \2"))


def temizle(metin):
    metin = metin.replace("**", "").replace("__", "").replace("*", "").replace("`", "")
    return re.sub(r"^[ \t]*#+(?:[ \t]+|$)", "", metin, flags=re.M).strip()


def yazim_esitle(metin):
    metin = re.sub(r"^[ \t]*[-–—][ \t]+", "— ", metin.translate(SAPKASIZ), flags=re.M)
    for desen, yeni in BITISIK:
        metin = re.sub(desen, yeni, metin)
    return metin


def bicim_esitle(metinler):
    satirlar = [[s.strip() for s in yazim_esitle(temizle(metin)).splitlines() if s.strip()]
                for metin in metinler]
    if any(not s for s in satirlar):
        raise AkisHatasi("boş metin")
    ayirac = "\n\n" if all(len(s) > 1 for s in satirlar) else " "
    return [ayirac.join(s) for s in satirlar]


def okur_istem(metin, alinti=3):
    """Okura biçimi eşitlenmiş tek metni ver. alinti: okurun yazacağı en çok yapay yer (3 iken hakem istemiyle aynı)."""
    metin = bicim_esitle([metin])[0].strip().translate(str.maketrans("’‘“”", "''\"\""))
    return f"""Aşağıda bir Türkçe metin var. Metni ya ana dili Türkçe olan bir insan ya da bir yapay zeka modeli yazdı. Bu setteki bazı metinleri insanlar, bazılarını yapay zeka yazdı. Yazım ve boşluk hataları düzeltildi; tırnaklar ve şapkalı harfler bütün metinlerde aynı biçime getirildi. Metinlerin uzunluğu farklı olabilir, bu bir ipucu değildir. Kararını dile göre ver: söz dizimi, sözcük seçimi, akış ve ritim.

Görev:
1. Metnin insan yazısı olma olasılığını 0 ile 100 arasında puanla (0 kesin yapay zeka, 50 kararsızım, 100 kesin insan).
2. Metne doğallık puanı ver: 1 çok yapay, 5 çok doğal. Doğallık, metnin Türk bir okura ne kadar akıcı ve kendiliğinden geldiğidir.
3. Yapay gelen en çok {alinti} yeri kısa alıntıyla yaz. Yoksa listeyi boş bırak.
4. Kararını bir iki cümleyle açıkla.

Yanıtı yalnız şu JSON biçiminde ver, başka hiçbir şey yazma:
{{"insan_olasilik": 0, "dogal": 0, "yapay": [], "gerekce": ""}}

Metin:
{metin}"""


# Okur kilidi (20.11.2026): kilitli sınavın 45 görevinde uçtan uca ağır değişiklikli görev 9'dan 8'e, gerçek bulgu
# 37'den 32'ye; doğallık iki hakemde +0,19 [-1,91, +2,36]. olcum.fikir_tara.KILIT ile aynı cümle.
KILIT = ("Yeniden yazdığın her yerde kim, neyi, ne zaman ve hangi koşulda yapacak, aynen kalsın: bir isteği ya da "
         "söylenen bir şeyi koşula bağlama, \"tamamı, yalnız, başlıca\" gibi kapsam sözlerini atma, metinde olmayan "
         "bir ayrıntı (iletişim yolu, sıra, gerekçe, biçim, yer) ekleme. ")


# Okur adımında anlam için kaynak (tarama 21.11.2026, Codex plan incelemesi: okur turu yalnız önceki metni görüyordu).
# İkinci tur kaynağı görünce (terzi-v13i-o2s) yalından +9,31 (%31,8), kör ağır 10 / yalın 4; kaynaksız ikinci tur
# (terzi-v13i-o2) +13,11, ağır 16 / 2.
OKUR_KAYNAK = ("\n\nBu metin aşağıdaki kaynaktan üslup için yeniden yazıldı. Kaynak yalnız anlam içindir: yeniden "
               "yazdığın her yer kaynaktaki anlamı taşısın (bir istek ya da zorunluluğun gücü, koşul, kapsam, sayı, ad "
               "ve sav aynı kalsın). Kaynağın söyleyişini kopyalama.\n\nKaynak:\n")


def yeniden_istem(metin, tur, yapay, gerekce, kilit=True, kaynak=None):
    """Ölçümdeki olcum.fikir_tara.okur_istem(kilit=True) ile aynı onarım istemi; kilit=False v1.1 sınavındaki istem.
    kaynak: verilirse istemin sonuna anlam için kaynak metin eklenir (OKUR_KAYNAK)."""
    yerler = "\n".join(f"- «{y}»" for y in yapay)
    return (f"Bir Türkçe metin ({tur}) var. Bir okur, metinde şu yerleri yapay zekâ yazısı gibi buldu:\n{yerler}\n"
            f"Okurun gerekçesi: {gerekce}\n\n"
            "Bu yerleri ve metinde aynı kalıpla yazılmış benzer yerleri, ana dili Türkçe olan bir insanın yazacağı "
            "gibi yeniden yaz. Bilgileri, sayıları ve adları koru; yeni bilgi ekleme. " + (KILIT if kilit else "")
            + "Metnin geri kalanına gerekmedikçe dokunma. Kullanıcıya soru soramazsın.\n"
            "Yanıt olarak yalnız metnin tamamını ver; açıklama ekleme.\n\nMetin:\n" + metin.strip()
            + ("" if kaynak is None else OKUR_KAYNAK + kaynak.strip()))


def _okur_kaydi(ham, alinti=3):
    nesne = re.search(r"\{.*\}", ham, re.S)
    if not nesne:
        raise ValueError("JSON yok")
    kayit = json.loads(nesne.group(0))
    for alan, alt, ust in (("insan_olasilik", 0, 100), ("dogal", 1, 5)):
        puan = kayit.get(alan)
        if type(puan) not in (int, float) or not alt <= puan <= ust:
            raise ValueError(f"geçersiz okur puanı: {alan}")
    yapay = kayit.get("yapay")
    if not isinstance(yapay, list):
        raise ValueError("okur alıntıları liste değil")
    return dict(insan_olasilik=kayit["insan_olasilik"], dogal=kayit["dogal"],
                yapay=[x for x in yapay if isinstance(x, str) and x.strip()][:alinti], gerekce=str(kayit.get("gerekce", "")))


def _oku(istem, okur, alinti=3):
    for deneme in range(2):
        ham = okur(istem)
        try:
            return _okur_kaydi(ham, alinti)
        except ValueError as e:
            if deneme == 1:
                raise AkisHatasi(f"okur yanıtı iki kez başarısız: {e}") from e


def _denetle(kaynak, sonuc, model, siki=False):
    rapor = bilgi.denetle(kaynak, sonuc, model, siki=siki)
    if rapor.hata:
        rapor = bilgi.denetle(kaynak, sonuc, model, siki=siki)
    if rapor.hata:
        ad = "anlam" if siki else "bilgi"
        raise AkisHatasi(f"{ad} denetimi iki kez başarısız: {rapor.hata}")
    return rapor


def _yaz(yazar, istem):
    metin = yazar(istem).strip()
    if not metin:
        raise AkisHatasi("yazar boş metin döndürdü")
    return metin


def duzelt(metin, tur, yazar, okur, denetci, anlam_model=None, anlam=ANLAM_VARSAYILAN, kilit=True, okur_kilit=None,
           okur_turu=1, okur_kaynak=False, okur_alinti=3, son_okur=0, son_okur_kaynak=False, yama_turu=0,
           tekrar=False):
    """İnsan örnekleriyle düzelt, okurun işaretlediği yerleri yaz ve bilgiyi denetle.

    kilit=False: ilk yazımdaki ve okur adımındaki anlam kilidi cümleleri yok (tanı, 21.11.2026: v1.1 yöntemi aynı
    taslaklarda kilitli üründen +8,1 doğal; istem farkı yalnız bu iki cümle).
    okur_kilit: okur adımındaki kilit cümlesi; None ise kilit ile aynı (tanı, 21.11.2026: tek kilit denemesi,
    kilit=True ve okur_kilit=False).
    okur_turu: okur adımı kaç kez çalışır; her tur bir önceki turun metnini okur, sonra bilgi denetimi (tarama,
    21.11.2026: ikinci tur aynı hakem çalışmasında tek kilit ürününe +7,3).
    okur_kaynak: okur adımının yeniden yazımı anlam için kaynak metni de görür (OKUR_KAYNAK).
    okur_alinti: okurun bir turda gösterdiği en çok yapay yer (tarama 22.11.2026: ks akışında 72 okumanın
    hepsi 3 sınırına dayandı).
    son_okur: anlam döngülerinden sonra kaç okur turu daha çalışır (geliştirme 21.11.2026, terzi-v13i-o2: ikinci tur
    doğallığı yalından %45 üstüne çıkardı, ağır anlam hatası da arttı); son_okur_kaynak: bu turlar kaynağı görür.
    yama_turu: en sonda Claude anlam döngüsü (dongu.calistir, Opus denetim ve en küçük yama) kaç tur çalışır.
    tekrar: ilk yazım aynı bilgiyi ikinci kez veren cümleleri tek yere indirir (duzeltici.TEKRAR, v1.4 denemesi)."""
    okur_kilit = kilit if okur_kilit is None else okur_kilit
    if okur_turu < 1:
        raise ValueError("okur_turu en az 1 olmalı")
    if type(okur_alinti) is not int or okur_alinti < 1:
        raise ValueError("okur_alinti en az 1 olan bir tam sayı olmalı")
    for ad, deger in (("son_okur", son_okur), ("yama_turu", yama_turu)):
        if type(deger) is not int or deger < 0:
            raise ValueError(f"{ad} 0 ya da daha büyük bir tam sayı olmalı")
    if anlam not in ANLAM_KIPLERI:
        raise ValueError(f"geçersiz anlam kipi: {anlam}")
    if not metin.strip():
        raise AkisHatasi("boş metin: düzeltilecek bir şey yok")
    metin, yazar_notu = yazar_notu_ayir(metin)
    orn = duzeltme_ornekleri(metin, tur)
    sonuc = _yaz(yazar, ilk_istem(metin, tur, orn, kilit, tekrar))
    adimlar = ([dict(adim="yazar_notu", ayrildi=yazar_notu)] if yazar_notu else []) + [
        dict(adim="ilk_yazim", ornek_sayisi=len(orn), **({} if kilit else dict(kilit=False)),
             **(dict(tekrar=True) if tekrar else {}))]

    def onar(sonuc, rapor):
        return _yaz(yazar, duzeltici.bilgi_istem(metin, sonuc, rapor.satirlar(), tur))

    def bilgi_turu(sonuc):
        rapor = _denetle(metin, sonuc, denetci)
        adimlar.append(dict(adim="bilgi", rapor=rapor.sozluk(), onarim=rapor.sorun))
        return onar(sonuc, rapor) if rapor.sorun else sonuc

    def okur_adimi(sonuc, kaynakli, son=False):
        kayit = _oku(okur_istem(sonuc, okur_alinti), okur, okur_alinti)
        yapay = kayit["yapay"]
        if yapay:
            sonuc = _yaz(yazar, yeniden_istem(sonuc, tur, yapay, kayit["gerekce"], okur_kilit,
                                              kaynak=metin if kaynakli else None))
        adimlar.append(dict(adim="okur", yeniden_yazim=bool(yapay), **({} if okur_kilit else dict(kilit=False)),
                            **(dict(kaynak=True) if kaynakli else {}), **(dict(son=True) if son else {}),
                            **kayit))
        # son turlar geliştirmedeki gibi (olcum/okur2_tara.py): metin değişmediyse bilgi denetimi yok
        return bilgi_turu(sonuc) if yapay or not son else sonuc

    sonuc = bilgi_turu(sonuc)
    for _ in range(okur_turu):
        sonuc = okur_adimi(sonuc, okur_kaynak)

    model = yazar if anlam_model is None else anlam_model
    for kip in ANLAM_DONGULERI.get(anlam, ()):
        denetimler, onarim = [], 0
        for tur_no in range(3):
            rapor = _denetle(metin, sonuc, model, siki=kip)
            denetimler.append(rapor.sozluk())
            if not rapor.sorun or tur_no == 2:
                break
            yeni = onar(sonuc, rapor)
            if 2 * len(yeni.split()) < len(sonuc.split()):
                raise AkisHatasi(f"onarım metni çok kısa ({len(yeni.split())} kelime)")
            sonuc = yeni
            onarim += 1
        adimlar.append(dict(adim="anlam", kip=kip, denetimler=denetimler, onarim=onarim))
    for _ in range(son_okur):
        sonuc = okur_adimi(sonuc, son_okur_kaynak, son=True)
    if yama_turu:
        sonuc, turlar = dongu.calistir(metin, sonuc, tur, yazar, orn, yama_turu)
        adimlar.append(dict(adim="yama_dongusu", turlar=turlar))
    return Sonuc(sonuc, adimlar, yazar_notu)
