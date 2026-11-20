"""Belge düzeyindeki ölçüler: cümle sonu tekdüzeliği, ritim, açılış tekrarı, sayımlar.

Her ölçü işlevi (belge, kural, tur, bilgi) alır ve Bulgu listesi döner. Eşikler kural
kaydının `esik` alanından gelir; türe göre değişen eşik {genel = 1.0, hukuk = 2.5}
biçiminde yazılır.
"""
import re
import statistics
from collections import Counter
from dataclasses import dataclass

from . import ek
from .metin import sade


@dataclass
class Bulgu:
    kural: str
    ad: str
    sinif: str
    grup: str
    duzey: str
    agirlik: float
    bas: int
    son: int
    alinti: str
    mesaj: str
    oneri: str
    cumle: int = -1  # belge içindeki cümle sırası, belge düzeyi bulguda -1

    def sozluk(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def esik_al(kural, ad, tur, varsayilan):
    d = kural.esik.get(ad, varsayilan)
    if isinstance(d, dict):
        return d.get(tur, d.get("genel", varsayilan))
    return d


def bulgu(kural, bas, son, alinti, mesaj, cumle=-1, agirlik=None):
    return Bulgu(kural.kimlik, kural.ad, kural.sinif, kural.grup, kural.duzey,
                 kural.agirlik if agirlik is None else agirlik, bas, son, alinti, mesaj,
                 kural.oneri, cumle)


def _ozet(yazi, n=80):
    yazi = " ".join(yazi.split())
    return yazi if len(yazi) <= n else yazi[: n - 1] + "…"


def son_ek_tekduze(belge, kural, tur, bilgi):
    """Aynı cümle sonu ekinin art arda ya da baskın gelmesi."""
    cs = bilgi["duzyazi"]
    en_az = esik_al(kural, "en_az_cumle", tur, 6)
    if len(cs) < 3:
        return []
    siniflar = kural.esik.get("siniflar") or ["mAktAdIr", "mIştIr", "DIr"]
    dizi = esik_al(kural, "dizi", tur, 3)
    pay = esik_al(kural, "pay", tur, 0.6)
    sonlar = [bilgi["son_sinif"][id(c)] for c in cs]
    cikti = []
    i = 0
    while i < len(sonlar):
        j = i
        while j + 1 < len(sonlar) and sonlar[j + 1] == sonlar[i] and sonlar[i] in siniflar:
            j += 1
        if sonlar[i] in siniflar and j - i + 1 >= dizi:
            sozler = ", ".join(cs[k].kelimeler[-1].yazi for k in range(i, j + 1))
            cikti.append(bulgu(kural, cs[i].bas, cs[j].son, _ozet(sozler),
                               f"{j - i + 1} cümle art arda -{sonlar[i]} ile bitiyor: {sozler}",
                               bilgi["sira"][id(cs[i])]))
        i = j + 1
    if len(cs) >= en_az:
        sayim = Counter(s for s in sonlar if s)
        if sayim:
            en, adet = sayim.most_common(1)[0]
            if en in siniflar and adet / len(cs) >= pay:
                cikti.append(bulgu(kural, 0, 0, "",
                                   f"{len(cs)} cümlenin {adet} tanesi -{en} ile bitiyor"))
    return cikti


def ek_yogunluk(belge, kural, tur, bilgi):
    """Bir cümle sonu sınıfının 100 kelimedeki sıklığı."""
    hedef = kural.esik.get("sinif", "mAktAdIr")
    esik = esik_al(kural, "yuzde", tur, 1.0)
    en_az_kelime = esik_al(kural, "en_az_kelime", tur, 50)
    kelime = bilgi["kelime"]
    if kelime < en_az_kelime:
        return []
    say = 0
    for c in belge.cumleler:
        for i, k in enumerate(c.kelimeler):
            if hedef == "mAktAdIr":
                sonraki = None
                if i + 1 < len(c.kelimeler):
                    ara = belge.metin[k.son:c.kelimeler[i + 1].bas]
                    if not re.search(r"[.,;:!?)\]\"”»]", ara):
                        sonraki = c.kelimeler[i + 1].yazi
                evet, emin = ek.makta_mi(k.yazi, sonraki)
            else:
                s, emin = ek.son_sinif(k.yazi, bilgi["yol"])
                evet = s == hedef
            say += bool(evet and emin)
    oran = 100 * say / kelime
    if oran > esik:
        return [bulgu(kural, 0, 0, "", f"100 kelimede {oran:.1f} kez -{hedef} (eşik {esik})")]
    return []


def ritim(belge, kural, tur, bilgi):
    """Cümle uzunluklarının fazla düzenli olması (değişim katsayısı düşük)."""
    cs = bilgi["duzyazi"]
    en_az = esik_al(kural, "en_az_cumle", tur, 8)
    if len(cs) < en_az:
        return []
    uz = [len(c.kelimeler) for c in cs]
    ort = statistics.mean(uz)
    cov = statistics.pstdev(uz) / ort if ort else 0
    esik = esik_al(kural, "cov", tur, 0.35)
    cikti = []
    if cov < esik:
        cikti.append(bulgu(kural, 0, 0, "", f"cümle uzunlukları çok düzenli (değişim {cov:.2f}, eşik {esik})"))
    dizi = esik_al(kural, "benzer_dizi", tur, 0)
    if dizi:
        i = 0
        while i < len(uz):
            j = i
            while (j + 1 < len(uz) and uz[j + 1] >= 10 and uz[i] >= 10
                   and max(uz[i:j + 2]) - min(uz[i:j + 2]) <= 4):
                j += 1
            if j - i + 1 >= dizi:
                cikti.append(bulgu(kural, cs[i].bas, cs[j].son, _ozet(cs[i].yazi),
                                   f"{j - i + 1} cümle art arda benzer uzunlukta ({', '.join(map(str, uz[i:j + 1]))} kelime)",
                                   bilgi["sira"][id(cs[i])]))
            i = j + 1
    return cikti


def acilis_tekrar(belge, kural, tur, bilgi):
    """Cümlelerin aynı kelimeyle ya da listedeki bağlaçlarla açılması."""
    cs = bilgi["duzyazi"]
    en_az = esik_al(kural, "en_az_cumle", tur, 8)
    if len(cs) < en_az:
        return []
    pay = esik_al(kural, "pay", tur, 0.25)
    liste = kural.esik.get("liste")
    if liste:
        rx = re.compile(r"^(?:" + "|".join(liste) + r")\b")
        uyan = [c for c in cs if rx.search(c.sade.lstrip("\"'“«(—– "))]
        if len(uyan) / len(cs) > pay:
            ilk = uyan[0]
            sozler = ", ".join(sorted({" ".join(c.sade.split()[:2]) for c in uyan}))
            return [bulgu(kural, ilk.bas, ilk.son, _ozet(sozler),
                          f"{len(cs)} cümlenin {len(uyan)} tanesi bağlaçla açılıyor: {_ozet(sozler, 120)}")]
        return []
    ilkler = Counter(c.kelimeler[0].sade for c in cs if c.kelimeler)
    kelime, adet = ilkler.most_common(1)[0]
    if adet / len(cs) > pay and adet >= 3:
        return [bulgu(kural, 0, 0, kelime, f"{len(cs)} cümlenin {adet} tanesi \"{kelime}\" ile açılıyor")]
    return []


def ulac_kuyruk(belge, kural, tur, bilgi):
    """Cümlenin ikinci yarısında -ArAk ile eklenen yorum kuyruğu."""
    cs = bilgi["duzyazi"]
    en_az = esik_al(kural, "en_az_cumle", tur, 5)
    if len(cs) < en_az:
        return []
    pay = esik_al(kural, "pay", tur, 0.15)
    uyan = []
    for c in cs:
        n = len(c.kelimeler)
        for k in c.kelimeler[n // 2:]:
            if k.sade == "olarak":
                continue
            evet, emin = ek.ulac_mi(k.yazi)
            if evet and emin:
                uyan.append((c, k))
                break
    if len(uyan) / len(cs) > pay:
        c, k = uyan[0]
        return [bulgu(kural, k.bas, k.son, ", ".join(x[1].yazi for x in uyan[:5]),
                      f"{len(cs)} cümlenin {len(uyan)} tanesinin ikinci yarısında -ArAk kuyruğu var")]
    return []


def sayim(belge, kural, tur, bilgi):
    """Ham metinde desen sayımı: eşik sabit ya da kelime başına."""
    metin = bilgi["ortulu"]
    say, ilk = 0, None
    for d in kural._rx:
        for m in d.finditer(metin):
            say += 1
            ilk = ilk or m
    if not say:
        return []
    sabit = esik_al(kural, "sabit", tur, 0)
    her = esik_al(kural, "kelime_basina", tur, 0)
    sinir = max(sabit, bilgi["kelime"] // her if her else 0)
    if say > sinir:
        return [bulgu(kural, ilk.start(), ilk.end(), metin[ilk.start():ilk.end()].strip() or ilk.group(),
                      f"{say} kez (sınır {sinir})")]
    return []


UCLU = re.compile(r"\b([a-zçğıöşü]+(?: [a-zçğıöşü]+)?), ([a-zçğıöşü]+(?: [a-zçğıöşü]+)?) ve ([a-zçğıöşü]+(?: [a-zçğıöşü]+)?)\b")


def uclu(belge, kural, tur, bilgi):
    """Kısa öğeli üçlemeler: hızlı, güvenli ve kolay."""
    bul = []
    for c in bilgi["duzyazi"]:
        for m in UCLU.finditer(c.sade):
            bul.append((c, m))
    her = esik_al(kural, "bin_kelimede", tur, 4)
    en_az = esik_al(kural, "en_az", tur, 3)
    if len(bul) >= en_az and 1000 * len(bul) / max(1, bilgi["kelime"]) > her:
        c, m = bul[0]
        return [bulgu(kural, c.bas + m.start(), c.bas + m.end(), c.yazi[m.start():m.end()],
                      f"{len(bul)} üçleme ({1000 * len(bul) / bilgi['kelime']:.1f} / 1000 kelime)",
                      bilgi["sira"][id(c)])]
    return []


ISLEV_KUCUK = {"ve", "ile", "için", "ya", "da", "de", "bir", "ki", "veya", "ama"}


def baslik_buyuk(belge, kural, tur, bilgi):
    """Başlıkta her kelimenin büyük harfle başlaması (bağlaçlar dahil)."""
    cikti = []
    for b in belge.bloklar:
        if b.tur != "baslik":
            continue
        for c in b.cumleler:
            ws = [k for k in c.kelimeler if not k.yazi.isdigit()]
            if len(ws) < 3:
                continue
            buyuk = [k for k in ws if k.yazi[:1].isupper()]
            islev = [k for k in ws[1:] if sade(k.yazi) in ISLEV_KUCUK and k.yazi[:1].isupper()]
            if len(buyuk) == len(ws) and islev and not c.yazi.isupper():
                cikti.append(bulgu(kural, c.bas, c.son, c.yazi, "başlıkta her kelime büyük harfle başlıyor",
                                   bilgi["sira"][id(c)]))
    return cikti


TIRE = re.compile(r"—|(?<=\s)–(?=\s)|(?<=\w)--(?=\w|\s)|(?<=\s)--(?=\s)")
# Mevzuat madde başı: "MADDE 9 –", "GEÇİCİ MADDE 2 –", "EK MADDE 1 -" (Resmî Gazete biçimi).
MADDE_BASI = re.compile(r"\bMADDE\s+\d+[A-Za-z]?\s*[-–—]\s*$")


def uzun_tire(belge, kural, tur, bilgi):
    """Düz yazıda uzun tire. Satır başındaki konuşma çizgisi ve o satırlar sayılmaz."""
    metin = bilgi["ortulu"]
    cikti, konum = [], 0
    for satir in metin.split("\n"):
        if not satir.lstrip().startswith(("—", "–", "-")) and not re.match(r"\s*\|", satir):
            for m in TIRE.finditer(satir):
                if MADDE_BASI.search(satir[:m.end()]):
                    continue
                b = konum + m.start()
                alinti = belge.metin[max(0, b - 25):b + 25].replace("\n", " ")
                cikti.append(bulgu(kural, b, b + len(m.group()), alinti.strip(), "düz yazıda uzun tire"))
        konum += len(satir) + 1
    return cikti


def yigilma(belge, kural, tur, bilgi):
    """Yapay zekânın fazla kullandığı sözlerin yığılması (veriden: olcum.kural_aday).

    Sözlerin her biri insan Türkçesinde de geçer; iz olan, 100 kelimedeki yoğunluğun insan
    metinlerinin büyük çoğunluğunu aşmasıdır. Eşik türe göre verilir (olcum.yigilma_ayar).
    """
    kelime = bilgi["kelime"]
    if kelime < esik_al(kural, "en_az_kelime", tur, 80):
        return []
    say = Counter()
    ilk = None
    for c in belge.cumleler:
        for rx in kural._rx:
            for m in rx.finditer(c.sade):
                say[m.group().strip()] += 1
                ilk = ilk or (c, m)
    toplam = sum(say.values())
    yogun = 100 * toplam / kelime
    esik = esik_al(kural, "yuzde", tur, 2.0)
    if yogun > esik and len(say) >= esik_al(kural, "en_az_farkli", tur, 3):
        sozler = ", ".join(f"{w} ({n})" if n > 1 else w for w, n in say.most_common(8))
        c, m = ilk
        return [bulgu(kural, 0, 0, _ozet(sozler, 120),
                      f"yapay zekânın sık kullandığı sözler yığılmış: 100 kelimede {yogun:.1f} (eşik {esik}): {sozler}")]
    return []


ISLEVLER = {
    "yigilma": yigilma,
    "uzun_tire": uzun_tire,
    "son_ek_tekduze": son_ek_tekduze,
    "ek_yogunluk": ek_yogunluk,
    "ritim": ritim,
    "acilis_tekrar": acilis_tekrar,
    "ulac_kuyruk": ulac_kuyruk,
    "sayim": sayim,
    "uclu": uclu,
    "baslik_buyuk": baslik_buyuk,
}
