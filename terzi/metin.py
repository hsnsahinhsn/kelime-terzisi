"""Metni bloklara, cümlelere ve kelimelere ayırır.

Konumlar özgün metindeki karakter sırasıdır. Kod, bağlantı adresi ve HTML yorumu
aynı uzunlukta boşlukla örtülür; böylece bulgular özgün metne işaret eder.
"""
import re
from dataclasses import dataclass, field

HARF = "a-zA-ZçğıöşüÇĞİÖŞÜâîûÂÎÛ"
KELIME_RX = re.compile(rf"[{HARF}0-9]+(?:['’][{HARF}]+)?")
SADE = str.maketrans("âîûÂÎÛ’‘", "aiuAIU''")

LISTE_SONU = {"vb", "vs", "vd", "vb.g"}
KISALTMA = {
    "dr", "prof", "doç", "yrd", "uzm", "op", "av", "sn", "bkz", "vb", "vs", "örn", "mah", "cad",
    "sok", "no", "st", "ltd", "şti", "yy", "s", "c", "alb", "gen", "org", "kur", "bşk", "md",
    "ar", "gör", "öğr", "müh", "hz", "çev", "haz", "yay", "ed", "vd", "age", "a.g.e", "mr", "mrs",
    "inc", "co", "jr", "nr", "tel", "faks", "km", "cm", "mm", "kg", "gr", "sa", "dk", "sn",
}


def kucuk(s):
    """Türkçe küçük harf: I -> ı, İ -> i."""
    return s.replace("I", "ı").replace("İ", "i").lower()


def sade(s):
    """Karşılaştırma biçimi: Türkçe küçük harf, şapkasız, düz kesme işareti."""
    return kucuk(s).translate(SADE)


def _ort(m):
    return " " * (m.end() - m.start())


def ort(metin):
    """Kod bloğu, satır içi kod, HTML yorumu, adres ve bağlantı hedefini boşlukla örter."""
    t = re.sub(r"```.*?(```|\Z)", _ort, metin, flags=re.S)
    t = re.sub(r"<!--.*?-->", _ort, t, flags=re.S)
    t = re.sub(r"`[^`\n]+`", _ort, t)
    t = re.sub(r"\]\([^)\s]*\)", lambda m: "]" + " " * (m.end() - m.start() - 1), t)
    t = re.sub(r"(?:https?://|www\.)\S+?(?=[.,;:!?)»”\"']*(?:\s|$))|[\w.+-]+@[\w-]+\.[\w.]+?(?=[.,;:!?)]*(?:\s|$))", _ort, t)
    return t


@dataclass
class Kelime:
    yazi: str
    bas: int
    son: int

    @property
    def sade(self):
        return sade(self.yazi)

    @property
    def govde(self):
        """Kesme işaretinden önceki parça (Ankara'da -> ankara)."""
        return self.sade.split("'")[0]


@dataclass
class Cumle:
    yazi: str
    bas: int
    son: int
    blok: int
    sira: int
    kelimeler: list = field(default_factory=list)
    ortulu: str = ""  # kod ve adres boşlukla örtülmüş biçim (aynı uzunluk)

    @property
    def sade(self):
        return sade(self.ortulu or self.yazi).replace("\n", " ")


@dataclass
class Blok:
    tur: str  # paragraf, baslik, madde, alinti, tablo, diyalog
    yazi: str
    bas: int
    son: int
    sira: int
    cumleler: list = field(default_factory=list)


@dataclass
class Belge:
    metin: str
    bloklar: list

    @property
    def cumleler(self):
        return [c for b in self.bloklar for c in b.cumleler]

    def duzyazi_cumleleri(self):
        """Ritim ölçüleri için: paragraf ve diyalog cümleleri."""
        return [c for b in self.bloklar if b.tur in ("paragraf", "diyalog") for c in b.cumleler]

    @property
    def kelime_sayisi(self):
        return sum(len(c.kelimeler) for c in self.cumleler)


def kelimeler(yazi, bas=0):
    return [Kelime(m.group(), bas + m.start(), bas + m.end()) for m in KELIME_RX.finditer(yazi)]


def _blok_turu(satir, numarali_liste=False):
    s = satir.lstrip()
    if not s:
        return "bos"
    if s.startswith("#"):
        return "baslik"
    if s.startswith("|"):
        return "tablo"
    if s.startswith(">"):
        return "alinti"
    if s[:1] in "—–":
        return "diyalog"
    if re.match(r"[-*+•]\s+", s):
        return "madde"
    m = re.match(r"(\d{1,2})[.)]\s+(\S)", s)
    if m and (numarali_liste or m.group(1) == "1" or m.group(2).isupper() or m.group(2) in "*`\"“«("):
        return "madde"
    return "paragraf"


_ISARET = re.compile(r"^\s*(#{1,6}\s+|>\s*|[-*+•]\s+|\d{1,2}[.)]\s+|[—–]\s*)")


_SOZ = set("abcçdefgğhıijklmnoöprsştuüvyzqwxâîûABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZQWXÂÎÛ0123456789.")


def _bitis_mi(yazi, i, kapanis=False):
    """yazi[i] bir nokta ise, cümle sonu olup olmadığına bakar (geriye yalnız bir kelime tarar)."""
    j = i
    while j > 0 and yazi[j - 1] in _SOZ and i - j < 40:
        j -= 1
    sozcuk = yazi[j:i]
    if kapanis:  # "Notum 85." gibi: kapanış tırnağından önceki nokta cümle bitirir
        return True
    alt = sade(sozcuk).rstrip(".")
    if alt in LISTE_SONU:
        return True
    if alt in KISALTMA or "." in alt:
        return False
    if re.fullmatch(r"[A-ZÇĞİÖŞÜ]", sozcuk):  # baş harf: M. Kemal
        return False
    if re.fullmatch(r"\d{1,3}", sozcuk):  # sıra sayısı: 1. Dünya Savaşı
        return False
    return True


def cumle_bol(yazi, bas=0):
    """Bir bloğu cümlelere böler; (yazı, baş, son) üçlüleri döner."""
    sonuc, i0 = [], 0
    n = len(yazi)
    i = 0
    while i < n:
        ch = yazi[i]
        if ch in ".!?…":
            j = i
            while j + 1 < n and yazi[j + 1] in ".!?…\"'”’»)":
                j += 1
            k = j + 1
            if k >= n:
                break
            if yazi[k].isspace():
                m = k
                while m < n and yazi[m].isspace():
                    m += 1
                ileri = yazi[m] if m < n else ""
                if ileri and (ileri.isupper() or ileri.isdigit() or ileri in "\"“«'(—–-"):
                    kapanis = j > i and yazi[i + 1] in "\"'”’»)"
                    if ch != "." or _bitis_mi(yazi, i, kapanis):
                        parca = yazi[i0:k]
                        if parca.strip():
                            sonuc.append(parca)
                        i0 = k
            i = j + 1
            continue
        i += 1
    if yazi[i0:].strip():
        sonuc.append(yazi[i0:])
    cikti, konum = [], bas
    for p in sonuc:
        ic = len(p) - len(p.lstrip())
        b = konum + ic
        cikti.append((p.strip(), b, b + len(p.strip())))
        konum += len(p)
    return cikti


def _satirlar(metin):
    """(satır, baş) çiftleri."""
    konum = 0
    for satir in metin.split("\n"):
        yield satir, konum
        konum += len(satir) + 1


def coz(metin):
    """Metni Belge yapısına çevirir."""
    ortulu = ort(metin)
    satirlar = list(_satirlar(ortulu))
    numarali = sum(bool(re.match(r"\s*\d{1,2}[.)]\s+", s)) for s, _ in satirlar) >= 2
    bloklar, acik = [], None  # acik: birleşmekte olan paragraf [bas, son]
    for satir, bas in satirlar:
        tur = _blok_turu(satir, numarali)
        if tur == "paragraf":
            if acik is None:
                acik = [bas, bas + len(satir)]
            else:
                acik[1] = bas + len(satir)
            continue
        if acik is not None:
            bloklar.append(("paragraf", acik[0], acik[1]))
            acik = None
        if tur != "bos":
            bloklar.append((tur, bas, bas + len(satir)))
    if acik is not None:
        bloklar.append(("paragraf", acik[0], acik[1]))
    sonuc = []
    for sira, (tur, bas, son) in enumerate(bloklar):
        yazi = ortulu[bas:son]
        isaret = _ISARET.match(yazi)
        kayma = isaret.end() if isaret and tur != "paragraf" else 0
        govde = yazi[kayma:]
        blok = Blok(tur, metin[bas:son], bas, son, sira)
        if tur == "tablo":
            ic = govde.strip(" |")
            b0 = bas + kayma + govde.find(ic) if ic else bas
            parcalar = [(ic, b0, b0 + len(ic))]
        else:
            parcalar = cumle_bol(govde.replace("\n", " "), bas + kayma)
        for csira, (cyazi, cb, cs) in enumerate(parcalar):
            c = Cumle(metin[cb:cs], cb, cs, sira, csira, ortulu=ortulu[cb:cs])
            c.kelimeler = kelimeler(ortulu[cb:cs], cb)
            for k in c.kelimeler:
                k.yazi = metin[k.bas:k.son]
            if c.kelimeler:
                blok.cumleler.append(c)
        sonuc.append(blok)
    return Belge(metin, sonuc)
