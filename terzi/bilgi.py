"""Bilgi denetimi: düzeltilmiş metinde kaybolan, değişen ya da eklenen bilgiyi bir modele buldurur.

Anlam kilidi (anlam.py) kurallarla çalışır ve uyarılarının çoğu yanlış alarmdır (v1.0 sınavı: %97). Bu modül
aynı soruyu bir dil modeline sorar. Model çağrısı dışarıdan verilir (istem -> metin), böylece düzeltici ile aynı
akışta Claude, GPT ya da bir ajan kullanılabilir. v1.1'de döngü içi denetçi Sonnet'tir; düzeltici Opus.
"""
import json
import re
from dataclasses import asdict, dataclass, field

TURLER = ("eksik", "degisen", "eklenen")


@dataclass
class Rapor:
    eksik: list = field(default_factory=list)
    degisen: list = field(default_factory=list)
    eklenen: list = field(default_factory=list)
    hata: str = ""

    @property
    def sorun(self):
        return bool(self.eksik or self.degisen or self.eklenen)

    def sozluk(self):
        return asdict(self)

    def satirlar(self):
        s = [f"- Eksik bilgi: {x.get('kaynakta', '')!r}. {x.get('aciklama', '')}".rstrip() for x in self.eksik]
        s += [f"- Değişen bilgi: kaynakta {x.get('kaynakta', '')!r}, düzeltmede {x.get('duzeltmede', '')!r}. "
              f"{x.get('aciklama', '')}".rstrip() for x in self.degisen]
        s += [f"- Eklenen bilgi: {x.get('duzeltmede', '')!r}. {x.get('aciklama', '')}".rstrip() for x in self.eklenen]
        return s


def istem(kaynak, sonuc):
    return (
        "Aşağıda bir KAYNAK metin ve onun DÜZELTİLMİŞ hâli var. Düzeltme yalnız üslubu değiştirmeliydi.\n"
        "Kaynaktaki her bilgi birimini düzeltilmiş metnin tamamında ara: sayı, miktar, tarih, saat, süre, ad, "
        "yer, kurum, istek, karar, koşul, uyarı, olumsuzluk, artış ya da azalış yönü, \"olabilir\", \"yaklaşık\" "
        "gibi ihtiyat sözleri, alıntılar. Ayrıca düzeltilmiş metinde kaynakta olmayan yeni bir bilgi var mı bak.\n"
        "Şunlar fark değildir: üslup, sözcük seçimi, cümle sırası, birleştirilen ya da bölünen cümleler, aynı "
        "bilginin tekrarının silinmesi, eş anlamlı söyleyiş, açıkça aynı şeyi gösteren adıl, süs ya da nezaket "
        "sözlerinin atılması. Yalnız bilgi kaybını, değişikliğini ya da eklenmesini yaz; emin değilsen yazma.\n"
        "Yanıt olarak yalnız şu biçimde JSON ver, başka bir şey yazma:\n"
        '{"eksik": [{"kaynakta": "...", "aciklama": "..."}], '
        '"degisen": [{"kaynakta": "...", "duzeltmede": "...", "aciklama": "..."}], '
        '"eklenen": [{"duzeltmede": "...", "aciklama": "..."}]}\n'
        "Sorun yoksa üç liste de boş olsun.\n\n"
        f"KAYNAK:\n{kaynak.strip()}\n\nDÜZELTİLMİŞ:\n{sonuc.strip()}\n")


def siki_istem(kaynak, sonuc):
    """Anlam onarım turu için sıkı denetim (v1.1 sınavı: gevşek denetimden geçen metinlerin %41'inde kör
    sınıflandırma gerçek anlam değişikliği buldu: zorunluluğun olanağa dönmesi, kapsam, derece, eklenen ayrıntı).
    Ölçümdeki denetçi istem() ile kalır; bu istem yalnız düzelticinin kendi denetimidir."""
    return (
        "Aşağıda bir KAYNAK metin ve onun DÜZELTİLMİŞ hâli var. Düzeltme yalnız üslubu değiştirmeliydi; anlam "
        "aynı kalmalıydı.\n"
        "Düzeltilmiş metni cümle cümle kaynakla karşılaştır. Okurun yanlış öğreneceği ya da kaçıracağı her farkı "
        "bul:\n"
        "- sayı, miktar, tarih, saat, süre, ad, soyadı, unvan, hitap, yer, kurum;\n"
        "- kim ne yaptı: eylemi yapan, alan, veren;\n"
        "- olumsuzluk ve kapsamı; zorunluluk ile olanak (\"gerekir\" ile \"-abilir\"); koşul, sınır, istisna; "
        "kapsam (tek ile birkaç, hepsi ile bazısı, örnek ile tam liste);\n"
        "- ihtiyat ve derece (\"olabilir\", \"yaklaşık\", \"kalıcı\" ile \"derin\", \"en önemli\");\n"
        "- kaynağın bir yargısı, gerekçesi, uyarısı ya da okura verdiği bir talimat;\n"
        "- düzeltmede kaynakta olmayan yeni bir ayrıntı: sahne, sayı, neden, kişi, yöntem.\n"
        "Şunlar fark değildir: aynı iddiayı başka sözcükle ya da başka tonla söylemek, cümle sırası, birleştirilen "
        "ya da bölünen cümleler, tekrarın silinmesi, açıkça aynı şeyi gösteren adıl, süs ya da nezaket sözlerinin "
        "atılması, bilginin metnin başka bir yerinde verilmesi.\n"
        "Yanıt olarak yalnız şu biçimde JSON ver, başka bir şey yazma:\n"
        '{"eksik": [{"kaynakta": "...", "aciklama": "..."}], '
        '"degisen": [{"kaynakta": "...", "duzeltmede": "...", "aciklama": "..."}], '
        '"eklenen": [{"duzeltmede": "...", "aciklama": "..."}]}\n'
        "Sorun yoksa üç liste de boş olsun.\n\n"
        f"KAYNAK:\n{kaynak.strip()}\n\nDÜZELTİLMİŞ:\n{sonuc.strip()}\n")


def olgu_istem(kaynak, sonuc):
    """Anlam onarım turunun olgu kipi: yalnız olgu farkları. Sıkı kip, taslağın yapay yorum cümlelerini de geri
    getiriyordu (v1.0 sınavı taslağı S002: 193 kelimeden 298 kelimeye). Yorum ve değerlendirme cümlelerinin
    atılması ya da yumuşatılması burada fark sayılmaz; kartın 4. kuralı da değer yargısı yerine bilgiyi ister."""
    return (
        "Aşağıda bir KAYNAK metin ve onun DÜZELTİLMİŞ hâli var. Düzeltme yalnız üslubu değiştirmeliydi; olgular "
        "aynı kalmalıydı.\n"
        "Düzeltilmiş metni cümle cümle kaynakla karşılaştır. Okurun yanlış öğreneceği, yanlış uygulayacağı ya da "
        "kaçıracağı her olgu farkını bul:\n"
        "- sayı, miktar, tarih, saat, süre, ad, soyadı, unvan, hitap, yer, kurum;\n"
        "- kim ne yaptı: eylemi yapan, alan, veren; olayların sırası;\n"
        "- olumsuzluk ve kapsamı; zorunluluk ile olanak (\"gerekir\" ile \"-abilir\"); koşul, sınır, istisna; "
        "kapsam (tek ile birkaç, hepsi ile bazısı, örnek ile tam liste);\n"
        "- kesinlik ve ihtiyat (\"olabilir\", \"yaklaşık\", \"henüz bilinmiyor\");\n"
        "- okura verilen talimat, istek, uyarı ya da tarih sınırı;\n"
        "- düzeltmede kaynakta olmayan yeni bir olgu: sayı, neden, kişi, yöntem, olay.\n"
        "Şunlar fark değildir: aynı olguyu başka sözcükle ya da başka tonla söylemek, cümle sırası, birleştirilen "
        "ya da bölünen cümleler, tekrarın silinmesi, açıkça aynı şeyi gösteren adıl, süs ya da nezaket sözlerinin "
        "atılması, olgu taşımayan yorum, değerlendirme ve derece sözlerinin atılması ya da yumuşatılması, bilginin "
        "metnin başka bir yerinde verilmesi.\n"
        "Yanıt olarak yalnız şu biçimde JSON ver, başka bir şey yazma:\n"
        '{"eksik": [{"kaynakta": "...", "aciklama": "..."}], '
        '"degisen": [{"kaynakta": "...", "duzeltmede": "...", "aciklama": "..."}], '
        '"eklenen": [{"duzeltmede": "...", "aciklama": "..."}]}\n'
        "Sorun yoksa üç liste de boş olsun.\n\n"
        f"KAYNAK:\n{kaynak.strip()}\n\nDÜZELTİLMİŞ:\n{sonuc.strip()}\n")


def hedef_istem(kaynak, sonuc):
    """Sıkı denetimden sonra hedefli denetim. Sıkı onarımdan geçen 90 geliştirme metninde kalan ağır bulguların
    çoğunu (Claude okuması, 20.11.2026) sıkı denetim temiz saymıştı; kalıp: koşulsuz istek koşula bağlanıyor,
    kapsam sözü düşüyor, kaynakta olmayan küçük bir ayrıntı (kanal, biçim, sıra, gerekçe) ekleniyor. Bu istem
    yalnız bu üç türe bakar ve kaynaktaki her isteği tek tek sayar; örnekler geliştirme metinlerinden alınmadı.
    Codex ikinci görüşü (20.11.2026): her bulgu okurun neyi farklı anlayacağını söylesin (yanlış alarm azalsın)."""
    return (
        "Aşağıda bir KAYNAK metin ve onun DÜZELTİLMİŞ hâli var. Düzeltme yalnız üslubu değiştirmeliydi. Genel "
        "bir denetim yapıldı; sen yalnız genel denetimin çoğu zaman kaçırdığı üç tür farkı ara.\n\n"
        "1. İstek, talimat, söz ve kural. Kaynakta okurdan istenen, okura söz verilen ya da bir kurala bağlanan her "
        "şeyi tek tek bul: kim, neyi, ne zaman, hangi koşulda yapacak. Her birinin düzeltilmiş metindeki "
        "karşılığını bul. Koşulsuz bir istek koşula bağlandıysa (\"tarihi bize bildirin\" yerine \"değişirse haber "
        "verin\", \"katılabilirsiniz\" yerine \"vaktiniz olursa uğrayın\"), bir koşul ya da süre düştüyse, bir söz "
        "kaybolduysa, zorunluluk olanağa döndüyse ya da tersi olduysa, bir olumsuzluk ya da istisna değiştiyse "
        "yaz.\n"
        "2. Kapsam ve nicelik. \"tamamı, hepsi, yalnız, her, bazı, birkaç, ana, başlıca, en, çeşitli\" gibi "
        "sözleri izle. Sayılmamış bir çokluk sayıya döndüyse (\"çeşitli nedenler\" yerine \"üç neden\"), \"başlıca\" "
        "olan tam listeye döndüyse, sayılan şeyin birimi kaydıysa (öğrenci yerine sınıf) ya da \"tamamı\" gibi bir "
        "kapsam sözü düştüyse yaz.\n"
        "3. Eklenen ayrıntı. Düzeltilmiş metni cümle cümle oku. Kaynakta söylenmeyen ve bağlamdan da açıkça "
        "çıkmayan bir ayrıntı var mı: iletişim yolu (e-posta, telefon, yazılı), yöntem, biçim ya da yerleşim (bir "
        "çizelgeye, bir sütuna yazma), olayların sırası (önce, ardından, sonunda), gerekçe ya da duygu, yer, kişi, "
        "sayı, sonuç. Varsa yaz.\n\n"
        "Şunlar fark değildir: aynı şeyi gündelik dille ya da başka tonla söylemek; normal bir okurun iki metinden "
        "de aynı sonucu çıkardığı açıklık farkı; tekrarın, süsün ya da nezaket sözünün atılması; bilginin metnin "
        "başka bir yerinde verilmesi; cümle sırası.\n"
        "Bir farkı yazmadan önce iki metnin tamamını oku. Her bulguda iki metindeki ilgili yeri alıntıla ve "
        "açıklamada okurun neyi farklı anlayacağını ya da yapacağını söyle. Okur iki metinden aynı şeyi anlıyorsa ya "
        "da emin değilsen yazma.\n"
        "Yanıt olarak yalnız şu biçimde JSON ver, başka bir şey yazma:\n"
        '{"eksik": [{"kaynakta": "...", "aciklama": "..."}], '
        '"degisen": [{"kaynakta": "...", "duzeltmede": "...", "aciklama": "..."}], '
        '"eklenen": [{"duzeltmede": "...", "aciklama": "..."}]}\n'
        "Sorun yoksa üç liste de boş olsun.\n\n"
        f"KAYNAK:\n{kaynak.strip()}\n\nDÜZELTİLMİŞ:\n{sonuc.strip()}\n")


def coz(yanit, tam=False):
    """Model yanıtından Rapor; JSON bulunamazsa hata alanı dolar ve sorun yok sayılmaz.
    tam: üç listenin üçü de yanıtta olmalı ({} ya da başka bir nesne temiz sayılmaz; onarım turu için)."""
    m = re.search(r"\{.*\}", yanit or "", re.S)
    if not m:
        return Rapor(hata="JSON yok")
    try:
        d = json.loads(m.group(0))
    except ValueError as e:
        return Rapor(hata=f"JSON bozuk: {e}")
    if not isinstance(d, dict):
        return Rapor(hata="JSON nesne değil")
    r = Rapor()
    if tam and any(t not in d for t in TURLER):
        r.hata = "JSON'da eksik liste"
        return r
    for t in TURLER:
        v = d.get(t, [])
        if not isinstance(v, list):
            r.hata = f"{t} liste değil"
            v = []
        # Düz metin öge de bir sorundur: atılmaz, açıklama olarak saklanır.
        setattr(r, t, [x if isinstance(x, dict) else {"aciklama": str(x)} for x in v])
    return r


ISTEMLER = {False: istem, True: siki_istem, "siki": siki_istem, "olgu": olgu_istem, "hedef": hedef_istem}


def denetle(kaynak, sonuc, model, siki=False):
    """model: istem alır, metin döner. siki: anlam onarım turunun istemi (True ya da "siki", "olgu")."""
    return coz(model(ISTEMLER[siki](kaynak, sonuc)), tam=bool(siki))
