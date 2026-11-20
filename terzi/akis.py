"""Ölçülen v1.1 düzeltme akışı. Model çağrıları istem alır ve metin döner."""
import hashlib
import json
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path

from . import bilgi, denetci, duzeltici, havuz

# Kilitli v1.1 sınavı (20.11.2026, 75 metin, aynı kör sınıflandırma): ağır değişiklikli görev yaklaşık 29 -> 16;
# doğallık iki hakem ortalamasında yaklaşık -1,3 (yalının yine yaklaşık 4 puan önünde).
ANLAM_VARSAYILAN = "siki-hedef"
ANLAM_KIPLERI = ("olgu", "siki", "siki-hedef", "yok")
# Her kip sırayla çalışan denetim ve onarım döngüleridir (bilgi.ISTEMLER anahtarları). hedef: sıkı denetimin
# kaçırdığı istek ve koşul, kapsam, eklenen ayrıntı farkları (bilgi.hedef_istem).
ANLAM_DONGULERI = {"olgu": ("olgu",), "siki": ("siki",), "siki-hedef": ("siki", "hedef")}
GUNDELIK = set(havuz.TURLER)
PAKET = Path(__file__).resolve().parent


class AkisHatasi(RuntimeError):
    """Düzeltme akışı tamamlanamadı."""


@dataclass
class Sonuc:
    metin: str
    adimlar: list[dict]


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


def ilk_istem(metin, tur, orn):
    return duzeltici.istem(metin, tur, denetci.denetle(metin, tur), orn, kip="kisa", taban=None, bulgu=False)


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


def okur_istem(metin):
    """Okura biçimi eşitlenmiş tek metni ver."""
    metin = bicim_esitle([metin])[0].strip().translate(str.maketrans("’‘“”", "''\"\""))
    return f"""Aşağıda bir Türkçe metin var. Metni ya ana dili Türkçe olan bir insan ya da bir yapay zeka modeli yazdı. Bu setteki bazı metinleri insanlar, bazılarını yapay zeka yazdı. Yazım ve boşluk hataları düzeltildi; tırnaklar ve şapkalı harfler bütün metinlerde aynı biçime getirildi. Metinlerin uzunluğu farklı olabilir, bu bir ipucu değildir. Kararını dile göre ver: söz dizimi, sözcük seçimi, akış ve ritim.

Görev:
1. Metnin insan yazısı olma olasılığını 0 ile 100 arasında puanla (0 kesin yapay zeka, 50 kararsızım, 100 kesin insan).
2. Metne doğallık puanı ver: 1 çok yapay, 5 çok doğal. Doğallık, metnin Türk bir okura ne kadar akıcı ve kendiliğinden geldiğidir.
3. Yapay gelen en çok 3 yeri kısa alıntıyla yaz. Yoksa listeyi boş bırak.
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


def yeniden_istem(metin, tur, yapay, gerekce):
    """Ölçümdeki olcum.fikir_tara.okur_istem(kilit=True) ile aynı onarım istemi."""
    yerler = "\n".join(f"- «{y}»" for y in yapay)
    return (f"Bir Türkçe metin ({tur}) var. Bir okur, metinde şu yerleri yapay zekâ yazısı gibi buldu:\n{yerler}\n"
            f"Okurun gerekçesi: {gerekce}\n\n"
            "Bu yerleri ve metinde aynı kalıpla yazılmış benzer yerleri, ana dili Türkçe olan bir insanın yazacağı "
            "gibi yeniden yaz. Bilgileri, sayıları ve adları koru; yeni bilgi ekleme. " + KILIT
            + "Metnin geri kalanına gerekmedikçe dokunma. Kullanıcıya soru soramazsın.\n"
            "Yanıt olarak yalnız metnin tamamını ver; açıklama ekleme.\n\nMetin:\n" + metin.strip())


def _okur_kaydi(ham):
    nesne = re.search(r"\{.*\}", ham, re.S)
    if not nesne:
        raise ValueError("JSON yok")
    kayit = json.loads(nesne.group(0))
    for alan, alt, ust in (("insan_olasilik", 0, 100), ("dogal", 1, 5)):
        puan = kayit.get(alan)
        if type(puan) not in (int, float) or not alt <= puan <= ust:
            raise ValueError(f"geçersiz okur puanı: {alan}")
    yapay = kayit.get("yapay", [])
    if not isinstance(yapay, list):
        raise ValueError("okur alıntıları liste değil")
    return dict(insan_olasilik=kayit["insan_olasilik"], dogal=kayit["dogal"],
                yapay=[x for x in yapay if isinstance(x, str) and x.strip()][:3], gerekce=str(kayit.get("gerekce", "")))


def _oku(istem, okur):
    for deneme in range(2):
        ham = okur(istem)
        try:
            return _okur_kaydi(ham)
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


def duzelt(metin, tur, yazar, okur, denetci, anlam_model=None, anlam=ANLAM_VARSAYILAN):
    """İnsan örnekleriyle düzelt, okurun işaretlediği yerleri yaz ve bilgiyi denetle."""
    if anlam not in ANLAM_KIPLERI:
        raise ValueError(f"geçersiz anlam kipi: {anlam}")
    if not metin.strip():
        raise AkisHatasi("boş metin: düzeltilecek bir şey yok")
    orn = ornekler(metin, tur)
    sonuc = _yaz(yazar, ilk_istem(metin, tur, orn))
    adimlar = [dict(adim="ilk_yazim", ornek_sayisi=len(orn))]

    def onar(sonuc, rapor):
        return _yaz(yazar, duzeltici.bilgi_istem(metin, sonuc, rapor.satirlar(), tur))

    def bilgi_turu(sonuc):
        rapor = _denetle(metin, sonuc, denetci)
        adimlar.append(dict(adim="bilgi", rapor=rapor.sozluk(), onarim=rapor.sorun))
        return onar(sonuc, rapor) if rapor.sorun else sonuc

    sonuc = bilgi_turu(sonuc)
    kayit = _oku(okur_istem(sonuc), okur)
    yapay = kayit["yapay"]
    if yapay:
        sonuc = _yaz(yazar, yeniden_istem(sonuc, tur, yapay, kayit["gerekce"]))
    adimlar.append(dict(adim="okur", yeniden_yazim=bool(yapay), **kayit))
    sonuc = bilgi_turu(sonuc)

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
    return Sonuc(sonuc, adimlar)
