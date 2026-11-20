"""Kural kayıtları: TOML dosyalarından yüklenir, cümlelere uygulanır.

Her kural bir veri kaydıdır: kimlik, düzey, ağırlık, geçerli türler, desen, öneri,
kaynak ve "yakalamalı" ile "yakalamamalı" örnekleri. Desenler Türkçe küçük harfe ve
şapkasız biçime çevrilmiş cümleye uygulanır.
"""
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

KURAL_KLASORU = Path(__file__).parent / "kurallar"
DUZEYLER = {"guclu": 3, "orta": 2, "zayif": 1}
SINIFLAR = {"yz", "tdk", "uslup"}
TIPLER = {"kalip", "olcu"}
YERLER = {"her", "giris", "kapanis", "cumle_basi", "paragraf_basi"}
TURLER = {"genel", "ajan", "rapor", "blog", "kurumsal", "teknik", "haber", "ansiklopedik",
          "akademik", "hukuk", "anlati", "sosyal", "eposta"}

# Desen kısaltmaları: {EK} herhangi bir ek dizisi, {S} bir kelime.
KISA = {
    "{EK}": r"[a-zçğıöşü']*",
    "{S}": r"[a-zçğıöşü0-9']+",
    "{BIR}": r"(?:bir )?",
}


def derle(desen):
    for k, v in KISA.items():
        desen = desen.replace(k, v)
    return re.compile(desen)


@dataclass
class Kural:
    kimlik: str
    ad: str
    grup: str
    sinif: str
    duzey: str
    tip: str = "kalip"
    agirlik: float = 1.0
    desen: list = field(default_factory=list)
    haric: list = field(default_factory=list)  # eşleşmenin içinde ya da cümlede geçerse sayma
    islev: str = ""
    esik: dict = field(default_factory=dict)
    yer: str = "her"
    en_az: int = 1  # belgede en az bu kadar eşleşme olunca bildir
    yogunluk: float = 0.0  # 100 kelimede en az bu kadar eşleşme olunca bildir
    turler: list = field(default_factory=list)
    haric_turler: list = field(default_factory=list)
    aciklama: str = ""
    oneri: str = ""
    kaynak: str = ""
    yakalamali: list = field(default_factory=list)
    yakalamamali: list = field(default_factory=list)
    dosya: str = ""
    _rx: list = field(default_factory=list, repr=False)
    _harx: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        hata = []
        if self.duzey not in DUZEYLER:
            hata.append(f"düzey {self.duzey}")
        if self.sinif not in SINIFLAR:
            hata.append(f"sınıf {self.sinif}")
        if self.tip not in TIPLER:
            hata.append(f"tip {self.tip}")
        if self.yer not in YERLER:
            hata.append(f"yer {self.yer}")
        for t in self.turler + self.haric_turler:
            if t not in TURLER:
                hata.append(f"tür {t}")
        if self.tip == "kalip" and not self.desen:
            hata.append("desen yok")
        if self.tip == "olcu" and not self.islev:
            hata.append("işlev yok")
        if hata:
            raise ValueError(f"{self.kimlik}: " + ", ".join(hata))
        self._rx = [derle(d) for d in self.desen]
        self._harx = [derle(d) for d in self.haric]

    def gecerli(self, tur):
        if tur in self.haric_turler:
            return False
        return not self.turler or tur in self.turler or tur == "genel" and "genel" in self.turler

    def eslesmeler(self, sade_yazi, yalniz_bas=False):
        """Bir cümlenin sade biçiminde (bas, son) aralıkları.

        yalniz_bas: yalnız cümle başındaki eşleşmeler (önünde yalnız boşluk ve noktalama).
        """
        cikti = []
        for rx in self._rx:
            for m in rx.finditer(sade_yazi):
                if m.end() == m.start():
                    continue
                if yalniz_bas and sade_yazi[:m.start()].strip(" \"'“«(—–-*") != "":
                    continue
                parca = sade_yazi[m.start():m.end()]
                if any(h.search(parca) or h.search(sade_yazi) for h in self._harx):
                    continue
                if any(not (m.end() <= b or m.start() >= s) for b, s in cikti):
                    continue
                cikti.append((m.start(), m.end()))
        return sorted(cikti)


def yukle(klasor=KURAL_KLASORU):
    kurallar, gorulen = [], set()
    for yol in sorted(Path(klasor).glob("*.toml")):
        veri = tomllib.loads(yol.read_text(encoding="utf-8"))
        for kayit in veri.get("kural", []):
            k = Kural(**kayit, dosya=yol.name)
            if k.kimlik in gorulen:
                raise ValueError(f"{k.kimlik} iki kez tanımlı")
            gorulen.add(k.kimlik)
            kurallar.append(k)
    return kurallar
