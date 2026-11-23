"""Taslağın sonunda yazarın isteyene yazdığı notu metinden ayırır.

İnceleme 23.11.2026 (docs/v1.4-claude-taslak.md): sınav 3'te 50 Claude taslağının 9'u böyle bir notla bitiyordu ("Metin
yaklaşık 128 kelime", "Metne yıl eklemedim"), GPT taslaklarının hiçbiri; ürün notu iki metinde korudu ve hakem 3 ile 15
verdi (yalın 28). Not metnin parçası değildir: düzeltmeden önce ayrılır, değişmeden ayrıca verilir.
Kural sıkıdır (Codex incelemesi, 23.11.2026): blok metnin kendisinden ya da isteyenden açıkça söz etmeli. "Not: Başvurular
500 kelimeyi geçmemelidir", "Not: Faturayı da ekledim" ya da bir başlık çizgisinin altındaki bölüm metinde kalır.
Ayar: 28 gerçek son blokta 26 not ayrıldı, 2 içerik notu kaldı; 52 316 insan metninde hiçbir ayırma olmadı.
İkinci ve üçüncü inceleme (Codex, 23.11.2026): "en az 500 kelime olmalı" gibi bir koşul kelime sayımı sayılmaz. Notun her
cümlesi yazarın yorumu olarak tanınmalıdır: metne ya da verilen bilgiye değinir, "Bugün 22 Kasım 2026" gibi yazarın tarihini
verir, ya da birinci ya da ikinci kişiyle konuşur ve yazma işine değinir ("ayrıntı eklemedim", "daha kısa bir metin
isterseniz"). "Kargo ücretsizdir.", "Faturayı da ekledim." ya da "Siparişi iade edebilirsiniz." gibi bir cümle varsa
blok metinde kalır. Kendi başına not olmayan bir cümle gövdede ve notun not cümlelerinde geçmeyen bir sayı, ay ya da gün
adı taşıyorsa ("Ürün 5 Aralık'ta kargoya verilecek") yine yeni bilgidir ve blok kalır.
"""
import re
import unicodedata

# Ayırıcı çizgi: önünde boş satır ya da metin başı olmalı (yoksa üstündeki satırın başlık çizgisidir).
_AYIRAC = re.compile(r"(?:\A|\n[ \t]*\n)[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*(?:\n|\Z)")
_NOT_BASI = re.compile(r"^[\s*_(\[]*not[\s*_]*:", re.I)
# Metnin kelime sayısı ("Metin yaklaşık 170 kelime", "Başlık hariç 253 kelime"); "Başvurular 500 kelimeyi geçmemeli" değil.
_SAYIM = r"\b(?:metin|metn\w*|başlık\w*|dahil|hariç|yaklaşık|tam)\W+(?:[\w’']+\W+){0,5}?\d+\s*(?:kelime|sözcük)"
# Yazarın kendi işi ("eklemedim", "kullandım", "belirtmedim") ve kaynağa ya da metne bir değinme birlikte.
_YAZDIM = (r"\b(?:ekle|kullan|bırak|yaz|tut|koy|hesapla|kur|genişlet|et|uydur|çıkar|yap|kısalt|uzat|seç|belirt|tekrarla)"
           r"(?:ma|me)?[dt][ıiuü]m\b|(?:yamadı|yemedi|amadı|emedi)(?:m|ğım|ğim)\b")
_DEGINME = (r"\bverdiğ(?:iniz|in)\b|\bvermediğ(?:iniz|in)\b|\bverilen (?:bilgi|öz|sayı)|\bverilmedi\w*|\bmetn\w*|\bmetin\w*|\buydur\w*"
            r"|\bdoğrula\w*|\bkelime")
# İsteyene yayın öncesi iş ("Yayımlamadan önce doğrulayın", "Metni güncel haber olarak yayımlayacaksanız").
_ISTEK = (r"\b(?:yayımla|yayınla)\w*\W+(?:[\w’']+\W+){0,10}?(?:doğrula|güncelle|kontrol|ekle|karşılaştır|düzelt|teyit)\w*"
          r"|\bmetn\w*\W+(?:[\w’']+\W+){0,6}?yayımla\w*"
          r"|köşeli parantez\w*\W+(?:[\w’']+\W+){0,14}?(?:doldur|doğrula|bırak)\w*"
          r"|\bisterse(?:niz|n)\b\W+(?:[\w’']+\W+){0,6}?(?:metn|metin|kısalt|uzat|tamamla)\w*")
_YAZDIM_RE, _DEGINME_RE = re.compile(_YAZDIM, re.I), re.compile(_DEGINME, re.I)
_SAYIM_RE, _ISTEK_RE = re.compile(_SAYIM, re.I), re.compile(_ISTEK, re.I)
# Kelime sayısı bir koşulsa ("en az 500 kelime olmalıdır", "300 kelimeyi geçmemeli") yazarın sayımı değildir.
_KOSUL_RE = re.compile(r"\ben (?:az|fazla|çok)\b|\b(?:asgari|azami|olmalı\w*|geçme\w*|aşma\w*|sınır\w*)", re.I)
_CUMLE = re.compile(r"(?<=[.!?…])[\s*_)\]]*\s+")
_AYLAR = ("ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık",
          "pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar")
_SOMUT = re.compile(r"(?<!\d)\d+(?!\d)|\b(?:" + "|".join(_AYLAR) + r")\w*")
# Yazarın yorumu: isteyene sesleniş ("isterseniz", "değiştirebilirsin", "çıkarabilirsiniz") ya da yazarın bugünkü tarihi.
_SESLENIS_RE = re.compile(r"\bisterse(?:n|niz)\b|\w[rz](?:sın|sin|sun|sün)(?:ız|iz|uz|üz)?\b")
# Yazma işine değinme: isteyene seslenişte ayrıntı ya da istenen uzunluk ("ayrıntılı bilgi için arayın" değil); yazarın
# kendi işinde bunlara ek olarak eklemediği olgu ya da bilgi ("yeni bir olgu eklemedim").
_IS_SES = r"\bayrıntı(?!lı)\w*|\bdaha (?:kısa|uzun)\b|\b(?:kısalt|uzat|tamamla)\w*"
_IS_SES_RE, _IS_YAZ_RE = re.compile(_IS_SES), re.compile(_IS_SES + r"|\bolgu\w*|\bbilgi(?!lendir)\w*")
# Yazar bugünün tarihini verdiyse, metindeki tarihlerin geçtiğini ya da ileride olduğunu söyleyen cümle de yorumdur
# ("Bugün 22 Kasım 2026. Bu yılın 7 Ekim ve 4 Ekim tarihleri geçmiş durumda."); bugünün tarihi yoksa içerik sayılır.
_TARIH_YORUM_RE = re.compile(r"\btarih\w*\W+(?:[\w’']+\W+){0,4}?(?:geçmiş|geçti\w*|ileri)")
_BUGUN_RE = re.compile(r"\bbugün(?:ün tarihi)?\W+\d{1,2}\s+(?:" + "|".join(_AYLAR[:12]) + r")")


def _kucuk(metin):
    return unicodedata.normalize("NFC", metin).replace("I", "ı").replace("İ", "i").lower()


def _cumleler(blok):
    return [c for c in _CUMLE.split(_kucuk(blok)) if c.strip()]


def _sayim_mi(b):
    return any(_SAYIM_RE.search(c) and not _KOSUL_RE.search(c) for c in _cumleler(b))


def not_mu(blok):
    """Blok metne ya da isteyene değinen bir yazar notu mu?"""
    b = _kucuk(blok)
    return bool(_sayim_mi(b) or _ISTEK_RE.search(b) or (_YAZDIM_RE.search(b) and _DEGINME_RE.search(b)))


def _yorum_mu(c):
    """Cümle yazarın yorumu mu: metne, verilen bilgiye ya da yazarın işine değinir, isteyene seslenir ya da tarih verir."""
    if not_mu(c) or _DEGINME_RE.search(c) or _BUGUN_RE.search(c):
        return True
    return bool(_YAZDIM_RE.search(c) and _IS_YAZ_RE.search(c) or _SESLENIS_RE.search(c) and _IS_SES_RE.search(c))


def _somutlar(metin):
    """Sayılar ve ay ya da gün adları; ad en uzun eşleşen köke indirilir ("cumartesi" "cuma" sayılmaz)."""
    sonuc = set()
    for m in _SOMUT.finditer(metin):
        w = m.group(0)
        sonuc.add(w if w[0].isdigit() else max((a for a in _AYLAR if w.startswith(a)), key=len))
    return sonuc


def _yeni_bilgi(not_, govde):
    """Notta metinde kalması gereken bilgi var mı? Bir cümle yazarın yorumu değilse ya da kendi başına not olmayan bir
    cümle gövdede ve notun not cümlelerinde geçmeyen sayı, ay ya da gün adı taşıyorsa evet. (S071: "metni 190'a
    tamamlayayım" sayısı önceki not cümlesinde de geçer.)"""
    cumleler = _cumleler(not_)
    bugunlu = any(_BUGUN_RE.search(c) for c in cumleler)
    if not all(_yorum_mu(c) or bugunlu and _TARIH_YORUM_RE.search(c) for c in cumleler):
        return True
    bilinen = _somutlar("\n".join([_kucuk(govde), *(c for c in cumleler if not_mu(c))]))
    return any(_somutlar(c) - bilinen for c in cumleler if not not_mu(c) and not _BUGUN_RE.search(c))


def _paragraflar(metin):
    return [p for p in re.split(r"\n[ \t]*\n", metin) if p.strip()]


def ayir(metin):
    """(gövde, not): taslağın sonundaki yazar notunu ayırır; not yoksa (metin, "")."""
    duz = metin.replace("\r\n", "\n").replace("\r", "\n").rstrip()
    ayiraclar = list(_AYIRAC.finditer(duz))
    if ayiraclar:
        son = ayiraclar[-1]
        govde, not_ = duz[:son.start()].rstrip(), duz[son.end():].strip()
        par = _paragraflar(not_)
        if (govde.strip() and par and len(par) <= 3 and len(not_.split()) <= 120 and all(map(not_mu, par))
                and not _yeni_bilgi(not_, govde)):
            return govde, not_
    par = _paragraflar(duz)
    if len(par) > 1:
        not_ = par[-1].strip()
        govde = "\n\n".join(p.strip("\n") for p in par[:-1]).rstrip()
        if _NOT_BASI.match(not_) and len(not_.split()) <= 80 and not_mu(not_) and not _yeni_bilgi(not_, govde):
            return govde, not_
    return metin, ""
