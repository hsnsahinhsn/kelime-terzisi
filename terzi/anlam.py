"""Türkçe metnin düzeltilmiş halinde anlam değişikliği işaretlerini bulur."""
import argparse, json, re, unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
from pathlib import Path

@dataclass
class Fark:
    tur: str
    duzey: str
    kaynakta: str
    sonucta: str
    ayrinti: str

HARF = r"[^\W\d_]"
KELIME = rf"{HARF}+(?:['’]{HARF}+)?"
TARIH = r"[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4}(?![0-9])"
SAAT = r"(?:[01]?[0-9]|2[0-3])[.:][0-5][0-9](?![0-9])"
RAKAM = r"(?:(?<!\w)[−-])?(?:[0-9]{1,3}(?:\.[0-9]{3})+(?![0-9])|[0-9]+)(?:,[0-9]+)?"
SAYI = re.compile(rf"{TARIH}|{SAAT}|{RAKAM}")
KISALTMA = r"(?:(?i:dr|prof|doç|av|sn|op|uzm|yrd)|[A-ZÇĞİÖŞÜÂÎÛ])\."
PARCA = re.compile(rf"(?:{SAYI.pattern})(?:['’]{HARF}+)?|{KISALTMA}|{KELIME}|\n[^\S\n]*\n|[^\s]")
KOD = re.compile(r"(?<![\\`])(`+)(?!`).*?(?<!`)\1(?!`)", re.S)
PARAGRAF = re.compile(r"(\r?\n[^\S\r\n]*\r?\n)")
URL = re.compile(r'''\b(?:https?://|ftp://|www\.)(?:[^\s<>()"“”«»]|\([^\s<>()]*\))+''', re.I)
ALINTI = re.compile(r'«([^»]*)»|“([^”]*)”|"([^"]*)"')
CEVIRI = str.maketrans("IİâîûÂÎÛ", "ıiaiuAIU")
BIRLER = dict(zip("bir iki üç dört beş altı yedi sekiz dokuz".split(), range(1, 10)))
ONLAR = dict(zip("on yirmi otuz kırk elli altmış yetmiş seksen doksan".split(), range(10, 100, 10)))
BASAMAK = {"bin": 1000, "milyon": 10**6, "milyar": 10**9}
SAYI_EK = re.compile(rf"({'|'.join((*BIRLER, *ONLAR, *BASAMAK, 'yüz', 'dörd'))})(?:y?[aeıiuü]|[dt][ae]n?|n?[ıiuü]n|y?l[ae])")
BAGLAM_DISI = set("ve veya ya yahut ile de da ki bir bu şu o için ise gibi olarak daha en".split())

OLUMSUZ_SON = (
    r"(?:l[ae]r)?(?:[mdknz]|[ıiuü]m|[ıiuü]z|n[ıiuü]z|s[ıiuü]n(?:[ıiuü]z)?|"
    r"[dt][ıiuü]r|[ydt][ıiuü](?:[kmnz]|l[ae]r)?|m[ıiuü]ş|[ıiuü]n(?:[ıiuü])?|[ıi]|se)?"
)
OLUMSUZ_EK = re.compile(
    rf"{HARF}+(?:m[ıiuü]yor|madı|medi|m[ae]z|mamış|memiş|mayacak|meyecek|mayacağ|meyeceğ|"
    rf"mamalı|memeli|madan|meden|mayan|meyen){OLUMSUZ_SON}"
)
OLUMSUZ_ISTISNA = re.compile(r"(?:az|biraz|kaz|yaz|namaz|elmadan|damadan|mezmur)$|(?:komedi|trajikomedi|dramedi)"
                             r"|(?:firma|forma|lamba|kama|hama|yama|zamba|plazma|prizma|dama|elma|kalma)(?:dan|dı|yı|ya)?$")
OLUMSUZ_SOZ = re.compile(rf"(?:değil|yok){OLUMSUZ_SON}")
SORU_FIILI = re.compile(r"(?:[dt][ıiuü](?:[mnk]|n[ıiuü]z|l[ae]r)?|[ıiuü]yor)$")
YUKARI = re.compile(r"artıyor|art(?!ık|ı(?:$|[lnsy])|çı)|yüksel|çoğal|büyü(?![kğ]|cü|le)|genişl(?:e|iyor)|hızlan|fazlalaş")
ASAGI = re.compile(r"azal|düş(?!ün|man|ey|ük)|geril(?:e|iyor)|küçül|daral|yavaşl(?:a|ıyor)|kısal")
IHTIYAT = set("muhtemelen belki galiba sanki görünüyor yaklaşık civarında neredeyse tahminen".split())
IDDIA = re.compile(r"iddia(?:lar)?(?:sı(?:na|nı|nın|nda|ndan)?|y[ıa]|dan?|nın|m(?:a|ı)?)?")
YETERLIK = re.compile(r"[ae]bil(?:ir|ecek|eceğ)(?:[a-zçğıöşü]*)$")

def _temizle(metin):
    def url_yerine(eslesme):
        adres = eslesme[0]
        return " " + adres[len(adres.rstrip(".,;:!?")):]
    return URL.sub(url_yerine, "".join(KOD.sub(" ", p) for p in PARAGRAF.split(metin)))

def _katla(metin):
    return metin.translate(CEVIRI).lower()

def _cumleler(metin):
    parcalar = []
    for parca in PARCA.findall(metin):
        if parca in (".", "!", "?", "…") or parca.startswith("\n"):
            if parcalar:
                yield [*parcalar, "?"] if parca == "?" else parcalar
                parcalar = []
        else:
            parcalar.append(parca)
    if parcalar:
        yield parcalar

def _kok(kelime):
    return re.split("['’]", kelime, maxsplit=1)[0]

def _adlar(cumleler, yalniz):
    adlar = set()
    for cumle in cumleler:
        for i, parca in enumerate(p for p in cumle if p[0].isalnum()):
            kok = _kok(parca)
            kisaltma = len(kok) >= 2 and kok.isupper()
            # Kesme işareti ve tek sözcüklü girdi, cümle başında da ad işareti sayılır.
            buyuk_harfli = kok[0].isupper() and (i or kok != parca or yalniz)
            if not parca.endswith(".") and (kisaltma or buyuk_harfli):
                adlar.add(_katla(kok))
    return adlar

def _sayi_koku(parca):
    if parca in ("yüzde", "binde", "ona", "onu", "onun", "onda", "ondan"):
        return parca
    eslesme = SAYI_EK.fullmatch(parca)
    return eslesme[1].replace("dörd", "dört") if eslesme else parca

def _yuzluk(parcalar, i, bilesik):
    deger = 0
    bir = BIRLER.get(parcalar[i], 0)
    if bir and parcalar[i + 1] == "yüz":
        deger, i = bir * 100, i + 2
    elif parcalar[i] == "yüz":
        deger, i = 100, i + 1
    if parcalar[i] in ONLAR:
        deger, i = deger + ONLAR[parcalar[i]], i + 1
    if parcalar[i] in BIRLER and (parcalar[i] != "bir" or deger or bilesik or parcalar[i + 1] in BASAMAK):
        deger, i = deger + BIRLER[parcalar[i]], i + 1
    return str(deger) if deger else "", i

def _sayi(parcalar, i, yuzde):
    terimler, ust = [], 10**10
    while True:
        parca = _kok(parcalar[i])
        if SAYI.fullmatch(parca):
            deger, son = _rakamla(parca), i + 1
        else:
            deger, son = _yuzluk(parcalar, i, bool(terimler) or yuzde)
        katsayi = deger if terimler else deger.lstrip("-")
        gecerli = katsayi.replace(",", "").isdigit()
        carpan = BASAMAK.get(parcalar[son], 0)
        if 0 < carpan < ust and (gecerli or not deger):
            terimler.append((deger or "1", carpan))
            ust, i = carpan, son + 1
            continue
        if not terimler:
            return deger, son
        if not carpan and gecerli and len(deger.split(",", 1)[0]) <= 3:
            terimler.append((deger, 1))
            i = son
        return _topla(terimler), i

def _topla(terimler):
    with localcontext() as ctx:
        ctx.prec = sum(len(d) for d, _ in terimler) + 12
        toplam = sum(Decimal(d.lstrip("-").replace(",", ".")) * c for d, c in terimler)
    isaret = "-" if terimler[0][0].startswith("-") else ""
    return _rakamla(isaret + format(toplam, "f").replace(".", ","))

def _rakamla(parca):
    if re.fullmatch(TARIH, parca):
        gun, ay, yil = parca.split(".")
        return f"{gun.zfill(2)}.{ay.zfill(2)}.{yil}"
    if re.fullmatch(SAAT, parca):
        return parca.replace(".", ":").zfill(5)
    isaret = "-" if parca.startswith(("-", "−")) else ""
    tam, _, kesir = parca.lstrip("-−").replace(".", "").partition(",")
    tam, kesir = tam.lstrip("0") or "0", kesir.rstrip("0")
    return (isaret if tam != "0" or kesir else "") + tam + ("," + kesir if kesir else "")

def _sayilar(cumleler):
    baglamlar = defaultdict(Counter)
    for cumle in cumleler:
        parcalar = [_sayi_koku(p) for p in cumle] + [""]
        for j in range(1, len(cumle)):  # "bu yüzden", "o yüzden" bağlaçtır, sayı değil
            if cumle[j] == "yüzden" and cumle[j - 1] in ("bu", "şu", "o"):
                parcalar[j] = "yüzden"
        i, baglam = 0, ""
        while i < len(cumle):
            yuzde = parcalar[i] in ("%", "yüzde")
            bas = i + yuzde
            deger, son = _sayi(parcalar, bas, yuzde)
            if son > bas:
                baglamlar[("%" if yuzde else "") + deger][baglam] += 1
                i = son
                continue
            if cumle[i][0].isalpha() and cumle[i] not in BAGLAM_DISI and not yuzde:
                baglam = _kok(cumle[i])
            i += 1
    return baglamlar

def _sayi_baglam(kaynak, sonuc):
    for deger in sorted(kaynak.keys() & sonuc.keys()):
        eski, yeni = kaynak[deger], sonuc[deger]
        for once, sonra in zip(sorted((eski - yeni).elements()), sorted((yeni - eski).elements())):
            yield Fark("sayi_baglam", "zayif", once, sonra, f"{deger} sayısının önceki içerik sözcüğü değişti.")

def _olumsuz(cumle):
    neler = [i for i, p in enumerate(cumle) if p == "ne"]
    ciftler = sum(cumle[-1] != "?" or not SORU_FIILI.search(" ".join(cumle[a + 1:b]).rstrip(" ,;"))
                  for a, b in zip(neler[::2], neler[1::2]))
    return ciftler + sum(
        p in ("hiç", "hiçbir", "asla") or bool(OLUMSUZ_SOZ.fullmatch(p))
        or not OLUMSUZ_ISTISNA.match(p) and bool(OLUMSUZ_EK.fullmatch(p))
        for p in cumle
    )

def _yon(cumle):
    ikililer = list(zip(cumle, cumle[1:]))
    sabit = {i + 1 for i, (a, b) in enumerate(ikililer) if a == "art" and b == "arda"} | \
            {i for i, (a, b) in enumerate(ikililer) if a == "art" and b == "arda"}
    yukari = sum(bool(YUKARI.match(p)) for i, p in enumerate(cumle) if i not in sabit)
    yukari += ikililer.count(("daha", "fazla")) + ikililer.count(("daha", "çok"))
    asagi = sum(bool(ASAGI.match(p)) for p in cumle) + ikililer.count(("daha", "az"))
    return yukari, asagi

def _ihtiyat(cumle):
    toplam = sum(p in IHTIYAT or bool(IDDIA.fullmatch(p) or YETERLIK.search(p)) for p in cumle)
    for once, sonra in zip(cumle, cumle[1:]):
        toplam += (once == "öne" and sonra.startswith("sür")
                   or once.endswith(("dığı", "diği", "duğu", "düğü", "tığı", "tiği", "tuğu", "tüğü"))
                   and sonra.startswith("düşünül"))
    return toplam

def _eksik_eklenen(tur, kaynak, sonuc):
    for deger, adet in sorted((kaynak - sonuc).items()):
        yield Fark(tur, "guclu", deger, "", f"{adet} kez çıkarıldı.")
    for deger, adet in sorted((sonuc - kaynak).items()):
        yield Fark(tur, "guclu", "", deger, f"{adet} kez eklendi.")

def _adet_farki(tur, duzey, kaynak, sonuc, ayrinti):
    if kaynak != sonuc:
        yield Fark(tur, duzey, str(kaynak), str(sonuc), ayrinti)

def _yon_farki(kaynak, sonuc):
    eski, yeni = list(map(_yon, kaynak)), list(map(_yon, sonuc))
    for yon, i in (("Artış", 0), ("Azalış", 1)):
        yield from _adet_farki("yon", "guclu", sum(p[i] for p in eski), sum(p[i] for p in yeni),
                               f"{yon} işareti sayısı değişti.")
    for i, ((art, azal), (yeni_art, yeni_azal)) in enumerate(zip(eski, yeni), 1):
        if art > yeni_art and azal < yeni_azal:
            yield Fark("yon", "guclu", "artış", "azalış", f"{i}. cümlede yön tersine döndü.")
        elif azal > yeni_azal and art < yeni_art:
            yield Fark("yon", "guclu", "azalış", "artış", f"{i}. cümlede yön tersine döndü.")

def _alintilar(metin):
    # Kesme işaretinin düz ya da kıvrık yazılması alıntıyı değiştirmez.
    return Counter(next(p for p in eslesme.groups() if p is not None).replace("’", "'")
                   for eslesme in ALINTI.finditer(metin))

def karsilastir(kaynak: str, sonuc: str) -> list[Fark]:
    """Kaynak ve sonuç arasındaki anlam değişikliği işaretlerini döndürür."""
    kaynak, sonuc = _temizle(kaynak), _temizle(sonuc)
    eski, yeni = [list(_cumleler(unicodedata.normalize("NFC", m))) for m in (kaynak, sonuc)]
    yalniz = all(len(c) == 1 and len(c[0]) == 1 for c in (eski, yeni))
    adlar = [_adlar(c, yalniz) for c in (eski, yeni)]
    eski, yeni = [[_katla(p) for p in c] for c in eski], [[_katla(p) for p in c] for c in yeni]
    sayilar = [_sayilar(c) for c in (eski, yeni)]
    sayimlar = [Counter({s: b.total() for s, b in sayi.items()}) for sayi in sayilar]
    farklar = list(_eksik_eklenen("sayi", *sayimlar))
    farklar.extend(_sayi_baglam(*sayilar))
    farklar.extend(_eksik_eklenen("ad", *(Counter(a) for a in adlar)))
    farklar.extend(_adet_farki("olumsuz", "guclu", sum(map(_olumsuz, eski)), sum(map(_olumsuz, yeni)),
                               "Olumsuzluk sayısı değişti."))
    farklar.extend(_yon_farki(eski, yeni))
    farklar.extend(_adet_farki("ihtiyat", "zayif", sum(map(_ihtiyat, eski)), sum(map(_ihtiyat, yeni)),
                               "İhtiyat ifadesi sayısı değişti."))
    for alinti, adet in sorted((_alintilar(kaynak) - _alintilar(sonuc)).items()):
        farklar.append(Fark("alinti", "guclu", alinti, "", f"{adet} alıntı aynen korunmadı."))
    return farklar

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("kaynak", type=Path)
    p.add_argument("sonuc", type=Path)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    with args.kaynak.open(encoding="utf-8", newline="") as k, args.sonuc.open(encoding="utf-8", newline="") as s:
        farklar = karsilastir(k.read(), s.read())
    if args.json:
        print(json.dumps([asdict(f) for f in farklar], ensure_ascii=False))
    else:
        for f in farklar:
            print(f"{f.duzey} {f.tur} {f.kaynakta!r} → {f.sonucta!r}. {f.ayrinti}")
    return int(any(f.duzey == "guclu" for f in farklar))

if __name__ == "__main__": raise SystemExit(main())
