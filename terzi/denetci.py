"""Denetçi: kuralları metne uygular, bulguları ve puanı verir.

Üç sınıf ayrı tutulur:
- yz: yapay zeka izi (puana girer),
- tdk: yazım kuralı (TDK; puana girmez),
- uslup: kullanıcı ayarı olan üslup konuları (puana girmez, varsayılan kapalı olabilir).
"""
from dataclasses import dataclass, field

from . import ek, kural as kural_mod, olcu
from .metin import coz, ort
from .olcu import Bulgu

_KURALLAR = None


def kurallar():
    global _KURALLAR
    if _KURALLAR is None:
        _KURALLAR = kural_mod.yukle()
    return _KURALLAR


@dataclass
class Rapor:
    kelime: int
    cumle: int
    tur: str
    bulgular: list = field(default_factory=list)
    son_dagilim: dict = field(default_factory=dict)

    @property
    def yz(self):
        return [b for b in self.bulgular if b.sinif == "yz"]

    @property
    def puan(self):
        """100 kelimede yapay zeka izi ağırlığı."""
        if not self.kelime:
            return 0.0
        return round(100 * sum(b.agirlik for b in self.yz) / self.kelime, 2)

    def sozluk(self):
        return {"kelime": self.kelime, "cumle": self.cumle, "tur": self.tur, "puan": self.puan,
                "son_dagilim": self.son_dagilim, "bulgular": [b.sozluk() for b in self.bulgular]}


def _bilgi(belge, yol):
    duz = belge.duzyazi_cumleleri()
    son, sira = {}, {}
    for i, c in enumerate(belge.cumleler):
        sira[id(c)] = i
        if c.kelimeler:
            s, emin = ek.son_sinif(c.kelimeler[-1].yazi, yol, ilk=len(c.kelimeler) == 1)
            son[id(c)] = s if emin else None
    return {"duzyazi": duz, "son_sinif": son, "sira": sira, "kelime": belge.kelime_sayisi,
            "ortulu": ort(belge.metin), "yol": yol}


def _kapsam(belge, kural, bilgi):
    duz = bilgi["duzyazi"]
    if kural.yer == "giris":
        return duz[:2]
    if kural.yer == "kapanis":
        return duz[-2:]
    if kural.yer == "paragraf_basi":
        return [b.cumleler[0] for b in belge.bloklar if b.cumleler and b.tur in ("paragraf", "madde")]
    return belge.cumleler


def _kalip(belge, kural, tur, bilgi):
    adaylar = []
    for c in _kapsam(belge, kural, bilgi):
        sade_yazi = c.sade
        for bas, son in kural.eslesmeler(sade_yazi, yalniz_bas=kural.yer == "cumle_basi"):
            alinti = c.yazi[bas:son]
            adaylar.append(olcu.bulgu(kural, c.bas + bas, c.bas + son, alinti,
                                      kural.aciklama.split(".")[0], bilgi["sira"][id(c)]))
    if not adaylar:
        return []
    if len(adaylar) < kural.en_az:
        return []
    if kural.yogunluk and 100 * len(adaylar) / max(1, bilgi["kelime"]) < kural.yogunluk:
        return []
    return adaylar


def denetle(metin, tur="genel", secili=None, yol="karma", kapali=()):
    """Metni denetler. secili: yalnız bu kimlikler; kapali: kapatılan kimlikler."""
    belge = coz(metin)
    bilgi = _bilgi(belge, yol)
    bulgular = []
    for k in kurallar():
        if secili and k.kimlik not in secili:
            continue
        if k.kimlik in kapali or not k.gecerli(tur):
            continue
        if k.tip == "kalip":
            bulgular += _kalip(belge, k, tur, bilgi)
        else:
            bulgular += olcu.ISLEVLER[k.islev](belge, k, tur, bilgi)
    dagilim = {}
    for c in bilgi["duzyazi"]:
        s = bilgi["son_sinif"].get(id(c)) or "?"
        dagilim[s] = dagilim.get(s, 0) + 1
    bulgular.sort(key=lambda b: (-kural_mod.DUZEYLER[b.duzey], b.cumle if b.cumle >= 0 else 10 ** 6, b.bas))
    return Rapor(belge.kelime_sayisi, len(belge.cumleler), tur, bulgular, dagilim)


DUZEY_AD = {"guclu": "güçlü", "orta": "orta", "zayif": "zayıf"}
SINIF_AD = {"yz": "Yapay zekâ izi", "tdk": "Yazım (TDK)", "uslup": "Üslup (ayar)"}


def yazdir(rapor, en_cok=None, yalniz=None):
    """İnsan okuyacağı kısa rapor."""
    satir = [f"Kelime Terzisi: {rapor.kelime} kelime, {rapor.cumle} cümle, tür {rapor.tur}. "
             f"Yapay zekâ izi puanı {rapor.puan:.1f} (100 kelimede ağırlık)."]
    for sinif in ("yz", "tdk", "uslup"):
        bs = [b for b in rapor.bulgular if b.sinif == sinif and (not yalniz or b.duzey in yalniz)]
        if not bs:
            continue
        satir.append(f"\n{SINIF_AD[sinif]}: {len(bs)} bulgu")
        for b in bs[:en_cok] if en_cok else bs:
            yer = f"{b.cumle + 1}. cümle" if b.cumle >= 0 else "metin geneli"
            alinti = f" «{b.alinti}»" if b.alinti else ""
            satir.append(f"- [{b.kural} {DUZEY_AD[b.duzey]}] {yer}:{alinti} {b.mesaj}.")
            if b.oneri:
                satir.append(f"  Öneri: {b.oneri}")
    if len(satir) == 1:
        satir.append("Bulgu yok.")
    return "\n".join(satir)
