"""Türkçe ek çözümlemesi: denetçinin gereken kadarı.

İki yol var:
- dar: yüzey kuralları ve istisna listeleri (yalnız standart kitaplık).
- zeyrek: Zemberek'in Python sürümü (kuruluysa). Belirsiz kelimede yardımcıdır.

Her işlev (sonuç, emin) döner. Emin değilse denetçi o kelimede karar vermez.
"""
import functools
import logging
import re

from .metin import sade

# Cümle sonu sınıfları
SINIFLAR = ("mAktAdIr", "mIştIr", "DIr", "Iyor", "DI", "mIş", "Ar", "AcAk", "mAlI",
            "emir", "ad", "soru", "diger")

_K = r"(?:[ıi]m|s[ıi]n|[ıi]z|s[ıi]n[ıi]z|l[ae]r|[uü]m|s[uü]n|[uü]z|s[uü]n[uü]z)?"
KOK_DIR = {"müdür", "nadir", "kadir", "takdir", "tedbir", "tasvir", "tahrir", "tabir", "tekbir",
           "satır", "katır", "hatır", "batır", "tadır", "çadır", "kudur", "tandır", "kader",
           "mütedair", "nazır", "hazır", "kadir", "fakir", "devir", "tahdit"}
# Ettirgen fiil kökleri: buyrukta -DIr ile biter (kaldır, getir, değiştir).
ETTIRGEN = re.compile(r"(?:l[ae]şt[ıi]r|[ıiuü]şt[ıiuü]r|^(?:kaldır|bildir|öldür|güldür|döndür|indir|"
                      r"kandır|sürdür|getir|bitir|götür|artır|yaptır|yetir|aldır|dindir|"
                      r"yedir|içir|giydir|bindir|gönder|söndür|uyandır|durdur|doldur|bastır|kestir|"
                      r"yazdır|güldür|kızdır|sustur|oturt|yürüt|sildir|seçtir))$")
# -n ile biten köke gelen -DIr: ettirgen buyruk (uyandır, söndür) ya da bildirme (insandır, mümkündür);
# yüzeyden bilinmez, karma yolda zeyrek karar verir.
N_DIR = re.compile(r"n(?:d|t)[ıiuü]r$")
# Ünlüden sonra gelen -tIr bildirme eki olamaz: geniş zaman (anlatır, üretir) ya da kök (satır).
TIR_GENIS = re.compile(r"[aeıioöuülrnmyzvbcdgğ]t[ıiuü]r(?:l[ae]r|[ıi]m|s[ıi]n|[ıi]z)?$")
SURE_DIR = re.compile(r"(?:l[ae]r|zaman|süre|yıl|sene|ay|gün|saat|hafta|dakika|asır|yüzyıl|"
                      r"gece|sabah|akşam|ömür|ezel)(?:d|t)[ıiuü]r$")
DI_DEGIL = {"kendi", "şimdi", "hadi", "haydi", "yedi", "adı", "ordu", "kedi", "artı", "kutu",
            "ütü", "örtü", "sanki", "dedi̇", "ödü", "büdü", "kadı", "abdi", "mehdi", "efendi",
            "hindi", "zindi", "ırgadı", "altı", "üstü", "ötesi"}
MIS_DEGIL = {"yetmiş", "altmış", "dolmuş", "yemiş", "geçmiş", "ermiş", "kalmış"}
ACAK_DEGIL = {"gelecek", "yiyecek", "içecek", "giyecek", "yakacak", "açacak", "dayanacak"}
MALI_DEGIL = {"elmalı", "somali", "malı", "kemalı", "cemalı"}
MAZ_DEGIL = {"namaz", "biraz", "beyaz", "ayaz", "kiraz", "yaz", "kaz", "az", "naz", "arz", "maz",
             "çaz", "caz", "gaz", "boz", "saz", "tez", "söz", "göz", "yüz", "düz", "öz", "iz", "kız",
             "kuz", "muz", "tuz", "buz", "toz", "sez", "ez", "kez", "pez"}
MAK_AD = re.compile(r"^(?:ekmek|yemek|çakmak|kaymak|ırmak|parmak|damak|basamak|emek|yamak|ilmek|tokmak|"
                    r"kaymakam|yaprak)(?:t[ae]|ten|tan|te|ta|ler|lar)?")
AD_YUKLEM = {"var", "yok", "değil", "gibi", "kadar", "için", "lazım", "gerek", "şart", "mümkün",
             "evet", "hayır", "tamam", "üzere", "beri", "sonra", "önce", "dolayı", "rağmen"}
SORU = re.compile(r"^m[ıiuü](?:y[ıiuü]m|s[ıiuü]n|y[ıiuü]z|s[ıiuü]n[ıiuü]z|d[ıiuü]r|yd[ıiuü]|ym[ıiuü]ş|"
                  r"d[ıiuü]rl[ae]r)?$")
ARAK_DEGIL = {"gerek", "çeyrek", "yürek", "börek", "merak", "irak", "barak", "erek", "terek",
              "gerekçe", "kürek", "sıcak", "ürkek", "çerek", "bilek", "kerek", "dilek", "yaprak",
              "toprak", "kurak", "durak", "parlak", "korkak", "tırnak", "kaymak", "Arak"}


def _temiz(kelime):
    w = sade(kelime)
    if "'" in w:  # Ankara'dır -> ek kısmı korunur, gövde işaretle ayrılır
        govde, _, ek = w.partition("'")
        return govde, ek
    return w, None


@functools.lru_cache(maxsize=50000)
def son_sinif_dar(kelime):
    """Cümle sonundaki kelimenin sınıfı, yüzey kurallarıyla."""
    w, ek = _temiz(kelime)
    if ek is not None:
        # Özel ad ya da sayı + ek: yalnız bildirme ekine bakılır.
        if re.fullmatch(r"(?:d|t)[ıiuü]r(?:l[ae]r)?", ek):
            return "DIr", True
        if re.fullmatch(r"(?:y)?d[ıiuü]|t[ıiuü]", ek):
            return "DI", True
        return "ad", True
    if not re.search(r"[a-zçğıöşü]", w):
        return "diger", True
    if kelime[:1].isupper() and not kelime.isupper() and len(kelime) > 1:
        return "ad", True  # cümle ortasında büyük harfli kelime: özel ad
    if w in AD_YUKLEM or w in KOK_DIR:
        return "ad", True
    if SORU.match(w):
        return "soru", True
    if MAK_AD.match(w):
        return "ad", True
    if re.search(r"m[ae]kt[ae](?:d[ıi]r|y[ıi]m|s[ıi]n|y[ıi]z|s[ıi]n[ıi]z|d[ıi]rl[ae]r|l[ae]r)?$", w):
        return "mAktAdIr", True
    if re.search(r"m[ıiuü]ş(?:l[ae]r)?(?:t|d)[ıiuü]r(?:l[ae]r)?$", w):
        return "mIştIr", True
    if re.search(r"(?:d|t)[ıiuü]r(?:l[ae]r)?$", w):
        if w in KOK_DIR:
            return "ad", True
        if ETTIRGEN.search(w) or N_DIR.search(w):
            return None, False
        if TIR_GENIS.search(w):
            return "Ar", True
        if len(w) <= 4:
            return None, False
        return "DIr", True
    if re.search(r"(?:d|t)[ıiuü](?:m|n|k|n[ıiuü]z|l[ae]r)?$", w):
        if w in DI_DEGIL:
            return "ad", True
        return "DI", True
    if re.search(r"[ıiuü]?yor" + _K + "$", w):
        return "Iyor", True
    if re.search(r"m[ıiuü]ş" + _K + "$", w):
        if w in MIS_DEGIL:
            return None, False
        return "mIş", True
    if re.search(r"(?:y)?[ae]c[ae]k" + _K + "$", w) or re.search(r"[ae]c[ae]ğ(?:[ıi]m|[ıi]z)$", w):
        if w in ACAK_DEGIL:
            return None, False
        return "AcAk", True
    if re.search(r"m[ae]l[ıi]" + r"(?:y[ıi]m|s[ıi]n|y[ıi]z|s[ıi]n[ıi]z|l[ae]r)?$", w):
        if w in MALI_DEGIL:
            return None, False
        return "mAlI", True
    if re.search(r"[ae]b[ıi]l[ıi]r" + _K + "$", w):
        return "Ar", True
    if re.search(r"m[ae]z(?:s[ıi]n|l[ae]r|s[ıi]n[ıi]z)?$|m[ae]m$|m[ae]y[ıi]z$", w):
        if w in MAZ_DEGIL or len(w) <= 4:
            return None, False
        return "Ar", True
    if re.search(r"(?:l[ae]r)$", w):
        return None, False  # çoğul ad mı (insanlar), -lA fiilinin geniş zamanı mı (sağlar)
    if re.search(r"(?:[ae]r|[ıiuü]r)" + _K + "$", w):
        return None, False  # geniş zaman mı ad mı, yüzeyden bilinmez
    if re.search(r"(?:[ıiuü]n|[ıiuü]n[ıiuü]z|s[ıiuü]n|s[ıiuü]nl[ae]r|[ae]l[ıi]m|[ae]y[ıi]m)$", w):
        return None, False  # buyruk mu iyelik mi belirsiz
    return "ad", False


# ---- zeyrek yolu ----

@functools.lru_cache(maxsize=1)
def _zeyrek():
    try:
        logging.getLogger("zeyrek").setLevel(logging.ERROR)
        for ad in ("zeyrek", "zeyrek.morphology", "zeyrek.rulebasedanalyzer"):
            logging.getLogger(ad).setLevel(logging.ERROR)
        import zeyrek
        logging.disable(logging.INFO)
        a = zeyrek.MorphAnalyzer()
        logging.disable(logging.NOTSET)
        return a
    except Exception:
        return None


def zeyrek_var():
    return _zeyrek() is not None


_ZAMAN = {"Prog1", "Prog2", "Past", "Narr", "Aor", "Fut", "Neces", "Imp", "Opt", "Cond", "Desr",
          "Cop", "Ques"}


def _cozumle_sinif(morf):
    m = list(morf)
    if "Ques" in m:
        return "soru"
    son_cop = max((i for i, x in enumerate(m) if x == "Cop"), default=-1)
    son_past = max((i for i, x in enumerate(m) if x == "Past"), default=-1)
    son_narr = max((i for i, x in enumerate(m) if x in ("Narr",)), default=-1)
    if son_cop >= 0 and son_cop > son_past:
        if "Prog2" in m[:son_cop]:
            return "mAktAdIr"
        if "Narr" in m[:son_cop]:
            return "mIştIr"
        return "DIr"
    if son_past >= 0:
        return "DI"
    if son_narr >= 0:
        return "mIş"
    for anahtar, sinif in (("Prog1", "Iyor"), ("Prog2", "mAktAdIr"), ("Fut", "AcAk"),
                           ("Neces", "mAlI"), ("Aor", "Ar"), ("Imp", "emir"), ("Opt", "emir")):
        if anahtar in m:
            return sinif
    return "ad"


@functools.lru_cache(maxsize=50000)
def _zeyrek_cozum(kelime):
    a = _zeyrek()
    if a is None:
        return None
    try:
        sonuc = a._parse(kelime)
    except Exception:
        return []
    return [tuple(x[0].id_ for x in p.morphemes) for p in sonuc if p is not None]


@functools.lru_cache(maxsize=50000)
def son_sinif_zeyrek(kelime):
    cozumler = _zeyrek_cozum(kelime)
    if cozumler is None:
        return None, False
    if not cozumler:
        return "diger", False
    siniflar = [_cozumle_sinif(m) for m in cozumler]
    fiil = [s for s, m in zip(siniflar, cozumler) if _ZAMAN & set(m) and s != "ad"]
    aday = fiil or siniflar
    if len(set(aday)) == 1:
        return aday[0], True
    return None, False


def son_sinif(kelime, yol="karma", ilk=False):
    """Cümle sonu sınıfı. yol: dar, zeyrek ya da karma (önce dar, belirsizse zeyrek).

    ilk: kelime cümlenin de ilk kelimesi (büyük harf özel ad sayılmaz).
    """
    if ilk:
        kelime = kelime[:1].lower() + kelime[1:] if kelime[:1] not in "Iİ" else ("ı" if kelime[0] == "I" else "i") + kelime[1:]
    if yol == "dar":
        return son_sinif_dar(kelime)
    if yol == "zeyrek":
        return son_sinif_zeyrek(kelime)
    s, emin = son_sinif_dar(kelime)
    if emin or not zeyrek_var():
        return s, emin
    return son_sinif_zeyrek(kelime)


@functools.lru_cache(maxsize=50000)
def dir_turu(kelime, son_mu=False):
    """-DIr ile biten kelime: kopula, sure, kok ya da None (eşleşmez)."""
    w, ek = _temiz(kelime)
    if ek is not None:
        return ("kopula", True) if re.fullmatch(r"(?:d|t)[ıiuü]r(?:l[ae]r)?", ek) else (None, True)
    if not re.search(r"(?:d|t)[ıiuü]r(?:l[ae]r)?$", w):
        return None, True
    if w in KOK_DIR:
        return "kok", True
    if kelime[:1].isupper() and not son_mu:
        return "kok", False  # Abdulkadir: özel ad olabilir, karar verme
    if TIR_GENIS.search(w):
        return None, True  # geniş zaman ya da kök
    if re.search(r"(?:ş|ç|ğ)?(?:ş|ç)?[ıiuü]?(?:l[ae]r)d[ıiuü]r$", w) and re.match(r"^(?:şunlar|bunlar|onlar)", w):
        return "kopula", True
    if not son_mu and SURE_DIR.search(w):
        return "sure", True
    if (ETTIRGEN.search(w) or N_DIR.search(w)) and not re.search(r"m[ıiuü]şt[ıiuü]r$", w):
        return None, False
    if len(w) <= 4:
        return None, False
    return "kopula", True


@functools.lru_cache(maxsize=50000)
def ulac_mi(kelime):
    """-ArAk ulacı mı (olarak, yaparak). Kesmeli özel ad (Siverek'te) ulaç değildir."""
    w, ek_ = _temiz(kelime)
    if ek_ is not None:
        return False, True
    if not re.search(r"(?:arak|erek)$", w):
        return False, True
    if w in ARAK_DEGIL or len(w) <= 5 and w not in ("olarak", "alarak", "ederek", "bilerek"):
        return False, w in ARAK_DEGIL
    return True, True


MAKTA_BAGLI = {"ve", "olan", "olup", "olduğu", "olduğunu", "iken", "veya", "ama", "fakat", "ancak"}


@functools.lru_cache(maxsize=50000)
def makta_mi(kelime, sonraki=None):
    """-mAktA sürerlik eki mi (gelmekte, gelmektedir, gelmekteyiz).

    sonraki: ardından gelen kelime; virgül, nokta ya da metin sonu gelirse None.
    Yalın -mAktA'dan sonra bir kelime gelirse çoğunlukla mastar + bulunma ekidir
    (bulmakta zorlanıyor, terk etmekte özgür).
    """
    w, _ = _temiz(kelime)
    if MAK_AD.match(w) and not re.search(r"m[ae]kt[ae]d[ıi]r", w):
        return False, True
    if re.search(r"m[ae]kt[ae](?:d[ıi]r|y[ıi]m|s[ıi]n|y[ıi]z|s[ıi]n[ıi]z|d[ıi]rl[ae]r|l[ae]r|d[ıi]|ym[ıi]ş|yken)$", w):
        return True, True
    if re.search(r"m[ae]kt[ae]$", w):
        if sonraki is None or sade(sonraki) in MAKTA_BAGLI:
            return True, True
        return False, True
    return False, True
