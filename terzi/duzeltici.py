"""Hafif düzeltici: denetçinin bulduğu yerleri modele düzelttirir, sonra yeniden denetler.

Model çağrısı dışarıdan verilir (istem -> metin). Böylece aynı akış Claude, GPT ya da
bir ajan için kullanılır. Akış:
1. Denetle. Bulgu olmasa da metin düzeltilir: okurun yakaladığı izlerin çoğu (cilalı akış,
   eşit cümleler, şablon paragraf) kurala dökülmüyor. Yalnız bulgulu yerlere dokunmak için bulgusuz_gec=True.
2. Düzeltme istemi: bulgular, kısa yazım kartı, tür notu ve varsa insan üslup örnekleri. Kısa istem türlerinde
   (KISA_TURLER) yalnız bulgular ve bilgi koruma kuralı verilir.
3. Sonucu denetle ve anlam kilidiyle karşılaştır. Anlam bozulduysa ya da güçlü bulgu
   kaldıysa bir tur daha iste. En çok iki tur.
"""
import functools
from dataclasses import dataclass, field
from pathlib import Path

from .denetci import denetle


@functools.lru_cache(maxsize=1)
def kart():
    """Kısa yazım kartı (terzi/kart.md)."""
    return (Path(__file__).parent / "kart.md").read_text(encoding="utf-8").strip()

TUR_NOTU = {
    "haber": "Haber dili: ilk cümlede ne olduğunu, kimin, nerede yaptığını ver; amaç ve arka plan sonra gelir. -dı ile anlat. Konuşanı \"dedi\", \"açıkladı\" ile an; aynı fiilin eş anlamlılarını sırayla döndürme (belirtti, vurguladı, ifade etti, dile getirdi). Alıntılar aynen kalır.",
    "ansiklopedik": "Ansiklopedi dili tarafsız ve bilgi yoğun; uzun, çok bilgili cümleler olağandır, onları kısaltıp eşitleme. Tanımda -dır ya da geniş zaman uygundur ama her cümlede değil. \"Önemli\", \"büyük bir\", \"zengin\" gibi değer yargılarını at.",
    "akademik": "Akademik özette uzun, yan cümleli cümleler, edilgen yapı ve -mektedir, -mıştır sonları insan yazısında da olağandır. Kartın cümle sonu ve cümle uzunluğu maddeleri bu türde geçerli değil: cümleleri kısaltma, bölme ya da sadeleştirme. Yalnız denetçinin bulduğu yerleri ve açık şişirme sözlerini (\"önemli bir rol oynamaktadır\", \"bu bağlamda\") düzelt. -mektedir yığılmışsa bir kısmını, özellikle bulgularda, -mıştır ya da -dır yap; geniş zamana çevirme. Amaç, yöntem, bulgu sırası kalsın.",
    "hukuk": "Hukuk ve resmî metinde uzun, parantezli, -ır ve -acaktır kipli ağır cümleler türün kendisidir. Kartın cümle sonu ve cümle uzunluğu maddeleri bu türde geçerli değil: cümleleri kısaltma, bölme ya da sadeleştirme. Terimler, madde numaraları ve yapı değişmez. Yerleşik kalıplar (söz konusu, ilgili, -mektedir) kalır; yalnız açık çeviri kalıplarını ve denetçinin bulduğu yerleri düzelt.",
    "anlati": "Anlatıda duyguyu adlandırma, davranışla göster. \"İçini bir huzursuzluk kapladı\" gibi klişelerden kaçın. Konuşmalar satır başında konuşma çizgisiyle verilir.",
    "blog": "Blog yazısı konuşur gibi akar: birinci tekil şahıs, -iyor, kısa ve uzun cümle karışık. \"Peki ya siz?\" gibi bir soruyla ya da öğütle kapanma.",
    "kurumsal": "Kurumsal metinde bile broşür dilini at: \"heyecanla duyururuz\", \"öncü\", \"yenilikçi çözümler\", \"değer katmak\". Somut bilgi kalsın.",
    "rapor": "Raporda bulguyu sayıyla ver; \"kayda değer\", \"belirgin biçimde\", \"önemli ölçüde\" yerine farkı yaz. Başlık ve tablo düzeni kalsın.",
    "teknik": "Teknik belgede komut, kod, sürüm, dosya ve arayüz adları değişmez. Adımlar kısa ve emir kipinde kalır.",
    "eposta": "E-postada selam ve kapanış kalıbı kalsın. \"Umarım bu e-posta sizi iyi bulur\" gibi çeviri kalıplarını at; isteği açıkça yaz.",
    "sosyal": "Sosyal medyada kısa, konuşma dili. Yazarın emoji ve etiket alışkanlığı kalsın; etiket yığma.",
    "ajan": "Ajan yanıtı doğrudan cevapla başlar. \"Harika soru\", \"Elbette!\", \"Umarım yardımcı olur\" yok. Madde listesi yalnız adımlar için; sona özet koyma.",
}


GENEL_IZ = ("Okurlar yapay zekâ metnini en çok şunlardan tanıyor: fazla düzgün ve cilalı akış; hep aynı kısalıkta, "
            "pürüzsüz ve eşit ritimli cümleler; noktalı virgülle bağlanmış simetrik cümleler; retorik soruyla yapılan "
            "geçiş; her paragrafın bir giriş cümlesiyle açılıp toparlayıcı bir cümleyle kapanması; eşit parçalı "
            "listeler; bilgiyi değil değerlendirmeyi veren genel sözler; sondaki özet, ders ya da iyimser kapanış; "
            "Türkçeye çevrilmiş gibi duran kalıplar.\n"
            "Bunları kır ama cümleleri tek tek kısaltıp eşitleme: bu yeni bir yapay zekâ izidir. "
            "Uzun cümleler kalabilir; kimi yerde iki kısa cümleyi birleştir. Noktalı virgülü yalnız gerçekten "
            "gerekirse kullan. Türün olağan üslubunu ve ağırlığını koru. Kişisel ses ya da somut ayrıntı yoksa "
            "uydurma; elindeki bilgiyle yaz.")


# Biçimi ve terimi sabit türlerde az dokunmak, ötekilerde cümleyi yeniden kurmak daha iyi sonuç verdi
# (geliştirme seti, istem 2: hukuk, ansiklopedi, rapor kazandı; haber ve anlatı yalın istemin gerisinde kaldı).
SIKI_TURLER = {"hukuk", "akademik", "ansiklopedik", "rapor", "teknik"}
SIKI = "Metni baştan yazma; sorunlu yerleri düzelt, akışı bozan yerleri yeniden kur."
SERBEST = ("Gerekirse cümleleri yeniden kur, birleştir, böl ya da sırasını değiştir; girişi türün alışkanlığına göre "
           "kur. Bilgi ve anlam aynı kalsın. Taslağın kişi eklerini ve hitabını koru; abartılı samimiyeti, reklam "
           "sesini ve ünlemli soruları yumuşat, yeni coşku ekleme.")


# Kısa istem kullanılan türler. Geliştirme setinde uzun istem (kurallar, kart, genel izler) bu türlerde yalın istemin
# 4 ile 7 puan gerisinde kaldı (istem 3 ve 4); hukuk, ansiklopedi, akademik, haber ve teknikte önde. Bu türlerde
# yalın isteme denetçi bulguları ve bir uzunluk tabanı eklenir; serbest kümede istem 4'ten 1,7 puan iyi (istem 5).
# Taban, sınavın uzunluk sınırı (ortalama 0,90) için: yalın istem bu türlerde metni ortalama 0,87'ye indiriyor.
# Anlatıda kısa istem uzun istemden kötü çıktı (-7,9 ve -3,9), anlatı uzun istemde kalır.
KISA_TURLER = {"ajan", "kurumsal", "eposta", "sosyal", "blog", "rapor"}
DUZEN_SIKI = "3. Paragraf, başlık ve liste düzeni kalsın; yalnız süs için kullanılmış kalın yazıyı ve işaretleri kaldır."
DUZEN_SERBEST = ("3. Kod, komut, tablo ve gerçek adım listeleri kalsın. Bilgiyi etiketli kısa maddelere bölen listeyi ve "
                 "süs başlıklarını, tür el veriyorsa düz paragrafa çevir. Süs için kullanılmış kalın yazıyı kaldır.")


# v1.1 kısa istem kipinde türün yalnız biçim notu (bir cümle).
BICIM_NOTU = {
    "hukuk": "Madde numaraları, terimler ve resmî yapı değişmez.",
    "teknik": "Komut, kod, sürüm, dosya ve arayüz adları değişmez.",
    "akademik": "Terimler ile amaç, yöntem ve bulgu sırası kalır.",
    "haber": "Alıntılar aynen kalır.",
    "rapor": "Başlık ve tablo düzeni kalır.",
}


def kisa_istem(metin, tur, rapor, taban=85, bicim=False, ornekler=(), bulgu=True):
    ilk = (f"Aşağıdaki metni bir yapay zekâ yazdı. Tür: {tur}.\n"
           "Metindeki yapay zekâ izlerini gider, metni doğal bir Türkçeyle düzelt. Bilgileri, sayıları, adları ve "
           "anlamı koru; yeni bilgi ekleme.")
    if taban:
        ilk += f" Kısaltabilirsin ama metin kaynağın yüzde {taban}'inden kısa olmasın."
    if bicim and tur in BICIM_NOTU:
        ilk += " " + BICIM_NOTU[tur]
    parca = [ilk]
    bl = bulgu_listesi(rapor) if bulgu else ""
    if bl:
        parca.append("Bir denetçi şu yerleri buldu; bunları da düzelt:\n" + bl)
    if ornekler:
        ornek = "\n\n".join(f"Örnek {i}:\n{o.strip()}" for i, o in enumerate(ornekler, 1))
        parca.append("Bu türde insanların yazdığı kısa örnekler. Konularını ve sözlerini alma; yalnız cümle "
                     "kuruluşunu, ritmi ve kelime seçimini örnek al. Örneklerdeki yazım hatalarını alma; "
                     "metne yazım hatası ya da argo ekleme:\n" + ornek)
    parca.append("Kullanıcıya soru soramazsın; gereken kararları kendin ver.\n"
                 "Yanıt olarak yalnız düzeltilmiş metnin tamamını ver; önüne ya da sonuna açıklama ekleme.\n\nMetin:\n"
                 + metin.strip())
    return "\n\n".join(parca)


def bulgu_listesi(rapor, en_cok=12):
    satir = []
    metin = None
    for b in [x for x in rapor.bulgular if x.sinif in ("yz", "tdk")][:en_cok]:
        yer = f"{b.cumle + 1}. cümle" if b.cumle >= 0 else "metnin geneli"
        alinti = f" «{b.alinti}»" if b.alinti else ""
        satir.append(f"- {yer}:{alinti} {b.mesaj}. Öneri: {b.oneri}")
    return "\n".join(satir)


def istem(metin, tur, rapor, ornekler=(), uzunluk=(95, 105), kip="v10", taban=85, bulgu=True):
    """kip "v10": v1.0 sınav sürümü (kısa istem yalnız KISA_TURLER'de). kip "kisa": her türde kısa istem,
    biçim notu ve isteğe bağlı uzunluk tabanı (v1.1 geliştirmesi)."""
    if kip == "kisa":
        return kisa_istem(metin, tur, rapor, taban=taban, bicim=True, ornekler=ornekler, bulgu=bulgu)
    if tur in KISA_TURLER and not ornekler:
        return kisa_istem(metin, tur, rapor)
    parca = [f"Aşağıdaki Türkçe metni bir yapay zekâ yazdı. Tür: {tur}. Metni, ana dili Türkçe olan iyi bir "
             "yazarın elinden çıkmış gibi doğal kıl.",
             "Kurallar:\n"
             "1. Bilgiyi koru: sayılar, adlar, tarihler, alıntılar, olumsuzluklar, artış ve azalış yönü, "
             "\"olabilir\", \"yaklaşık\" gibi ihtiyat sözleri aynen kalır. Yeni bilgi, örnek, duygu ya da ayrıntı ekleme.\n"
             f"2. Uzunluk kaynak metnin yüzde {uzunluk[0]} ile {uzunluk[1]} arası kalsın. Bilgi taşımayan dolgu sözlerini silebilirsin.\n"
             + (DUZEN_SIKI if tur in SIKI_TURLER else DUZEN_SERBEST) + "\n"
             "4. Yazım hatası, argo ya da yapay \"insan pürüzü\" ekleme. " + (SIKI if tur in SIKI_TURLER else SERBEST) + "\n"
             "5. Bir sözü atarken yerine zorlama bir eş anlamlı koyma; doğal bir karşılığı yoksa sözü bırak. "
             "Değiştirdiğin her söz öbeğini cümlenin içinde sesli okur gibi denetle; doğal değilse daha yalın söyle.\n"
             "6. Kullanıcıya soru soramazsın; gereken kararları kendin ver.",
             GENEL_IZ]
    bl = bulgu_listesi(rapor)
    if bl:
        parca.append("Denetçinin bulduğu yerler (önce bunları düzelt):\n" + bl)
    parca.append(kart())
    if tur in TUR_NOTU:
        parca.append(TUR_NOTU[tur])
    if ornekler:
        ornek = "\n\n".join(f"Örnek {i}:\n{o.strip()}" for i, o in enumerate(ornekler, 1))
        parca.append("Bu türde insanların yazdığı kısa örnekler. Konularını ve sözlerini alma; yalnız cümle "
                     "kuruluşunu, ritmi ve kelime seçimini örnek al:\n" + ornek)
    parca.append("Yanıt olarak yalnız düzeltilmiş metnin tamamını ver; önüne ya da sonuna açıklama ekleme.\n\nMetin:\n"
                 + metin.strip())
    return "\n\n".join(parca)


def ikinci_istem(kaynak, sonuc, farklar, rapor, tur, bilgi_satirlari=()):
    sorun = list(bilgi_satirlari)
    for f in farklar:
        sorun.append(f"- Anlam ({f.tur}): kaynakta {f.kaynakta!r}, düzeltmede {f.sonucta!r}. {f.ayrinti}")
    for b in [x for x in rapor.yz if x.duzey == "guclu"][:6]:
        alinti = f" «{b.alinti}»" if b.alinti else ""
        sorun.append(f"- Yapay zekâ izi:{alinti} {b.mesaj}. Öneri: {b.oneri}")
    return (f"Bir Türkçe metni ({tur}) doğal kılmak için düzelttin. Denetim şu sorunları buldu:\n" + "\n".join(sorun)
            + "\n\nAnlam sorunlarında kaynak metne dön: bilgi kaynaktaki gibi olmalı. Başka yerleri değiştirme. "
              "Yanıt olarak yalnız düzeltilmiş metnin tamamını ver.\n\nKaynak metin:\n" + kaynak.strip()
            + "\n\nDüzeltilmiş metin:\n" + sonuc.strip())


def bilgi_istem(kaynak, sonuc, satirlar, tur):
    """Bilgi denetimi kipinde ikinci tur: yalnız bulunan bilgi sorunları giderilir. v1.1 A1'de ikinci tura giden
    görevler (%78) yalın istemin 3,1 puan, tek turda kalanlar 0,7 puan gerisindeydi; eski istemdeki "kaynak metne
    dön" metni taslağın söyleyişine geri çekiyordu."""
    return (f"Bir Türkçe metni ({tur}) doğal kılmak için düzelttin. Bir denetçi, düzeltmede kaynağa göre şu bilgi "
            "sorunlarını buldu:\n" + "\n".join(satirlar)
            + "\n\nYalnız bu sorunları gider: o bilgiler kaynaktaki gibi olsun. Düzeltilmiş metnin geri kalanını, "
              "üslubunu ve uzunluğunu koru; kaynak metnin söyleyişine dönme. Bir uyarı yanlışsa o yeri olduğu gibi "
              "bırak. Yanıt olarak yalnız düzeltilmiş metnin tamamını ver.\n\nKaynak metin:\n" + kaynak.strip()
            + "\n\nDüzeltilmiş metin:\n" + sonuc.strip())


@dataclass
class Sonuc:
    metin: str
    turlar: int
    once: float
    sonra: float
    farklar: list = field(default_factory=list)
    istemler: list = field(default_factory=list)
    bilgi: list = field(default_factory=list)  # her turun bilgi denetimi raporu (sözlük)
    metinler: list = field(default_factory=list)  # her turun çıktısı (son öge metin ile aynı)


def duzelt(metin, tur, model, ornekler=(), en_cok_tur=2, bulgusuz_gec=False, kip="v10", taban=85, bilgi_model=None,
           bulgu=True):
    """model: istem alır, metin döner. Sonuc döner.

    bilgi_model verilirse ikinci turu yalnız bilgi denetiminin (bilgi.py) bulduğu sorun tetikler: anlam kilidinin
    uyarıları (v1.0 sınavında %97'si yanlış alarm) ve kalan güçlü izler yalnız kaydedilir. Denetim yanıtı
    çözülemezse bir kez yinelenir; yine çözülemezse ikinci tur yapılmaz, hata kayıtta kalır."""
    from .anlam import karsilastir
    from . import bilgi
    r0 = denetle(metin, tur)
    if bulgusuz_gec and not [b for b in r0.bulgular if b.sinif in ("yz", "tdk")]:
        return Sonuc(metin, 0, r0.puan, r0.puan)
    ist = istem(metin, tur, r0, ornekler, kip=kip, taban=taban, bulgu=bulgu)
    sonuc = model(ist).strip()
    istemler = [ist]
    turlar = 1
    bilgiler = []

    def kontrol(sonuc):
        farklar = [f for f in karsilastir(metin, sonuc) if f.duzey == "guclu"]
        rapor = denetle(sonuc, tur)
        if bilgi_model is None:
            return farklar, rapor, None, bool(farklar)
        b = bilgi.denetle(metin, sonuc, bilgi_model)
        if b.hata:
            bilgiler.append(b.sozluk())
            b = bilgi.denetle(metin, sonuc, bilgi_model)
        bilgiler.append(b.sozluk())
        return farklar, rapor, b, b.sorun

    def tekrar(r1, anlam_sorunu):
        if bilgi_model is not None:
            return anlam_sorunu
        return anlam_sorunu or any(x.duzey == "guclu" for x in r1.yz)

    metinler = [sonuc]
    farklar, r1, b, anlam_sorunu = kontrol(sonuc)
    while turlar < en_cok_tur and tekrar(r1, anlam_sorunu):
        ist = (bilgi_istem(metin, sonuc, b.satirlar(), tur) if b is not None
               else ikinci_istem(metin, sonuc, farklar, r1, tur))
        istemler.append(ist)
        sonuc = model(ist).strip()
        metinler.append(sonuc)
        turlar += 1
        farklar, r1, b, anlam_sorunu = kontrol(sonuc)
    return Sonuc(sonuc, turlar, r0.puan, r1.puan, farklar, istemler, bilgiler, metinler)
