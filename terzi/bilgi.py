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


# Envanter denetimleri (21.11.2026, olcum/anlam_tara.py taraması, 36 taslağın iki kolu, doğru cevap kör GPT
# denetiminin ağır bulguları): Claude, okura etkiyi sorunca değişikliklerin çoğunu hafif sayıyor ve sıkı ile hedefli
# denetim tek kilit ürününün altı ağır hatasının hiçbirini bulmadı. Envanter önce kaynağın bilgi birimlerini sayar,
# sonra her birinin karşılığını alıntılatır: Opus ile 16/17 yakaladı. tur_istem aynı envantere tür yazdırır;
# onarıma yalnız bilgi türleri gider (duygu, nezaket, vurgu, süs sözleri gitmez).
ENVANTER_TANIM = (
    "Anlam değişikliği şudur: bir bilginin düşmesi ya da değişmesi (sayı, ad, tarih, yer, değişimin yönü); koşulsuz "
    "bir istek ya da sözün koşula bağlanması ya da bir koşulun düşmesi; bir isteğin düz bir söze ya da düz bir sözün "
    "isteğe dönmesi; bir kapsam sözünün düşmesi ya da değişmesi (\"tamamı\", \"yalnız\", \"başlıca\", \"en az\", "
    "\"yaklaşık\"); bir ihtiyat sözünün düşmesi ya da eklenmesi (\"olabilir\", \"yaklaşık\"); bir savın ya da sonucun "
    "başka bir savla değişmesi; kaynakta olmayan yeni ve somut bir ayrıntı (tarih, iletişim yolu, sıra, gerekçe, "
    "biçim, yer, kişi, olay). Aynı şeyi başka sözcüklerle söylemek değişiklik değildir.\n"
    "Her değişikliği ağır ya da hafif diye işaretle: okurun yapacağı ya da inanacağı şeyi değiştiriyorsa ağır "
    "(\"agir\": true), değiştirmiyorsa hafif (\"agir\": false).\n")
# Uçtan uca koşu (21.11.2026, terzi-v13-o2t): Sonnet taslaklarının sonundaki yazar notunu ("Yalnızca verdiğiniz
# bilgileri kullandım", kelime sayısı) envanter eksik saydı, onarım notu metne geri ekledi; hakem bu üç metne 1-4 verdi.
YAZAR_NOTU = (
    "Kaynağın başında ya da sonunda metnin kendisi olmayan, yazarın metni isteyene yazdığı bir not olabilir (örnek: "
    "kelime sayısı, hangi bilgilerin kullanıldığı, \"isterseniz kısaltırım\" gibi bir öneri). Bu notu envantere alma; "
    "düzeltmede düşmesi fark değildir.\n")


def envanter_istem(kaynak, sonuc):
    """Önce kaynağın bilgi envanteri, sonra madde madde eşleme: model iki metni gözden geçirip "aynı" demesin."""
    return (
        "Aşağıda bir KAYNAK metin ve onun DÜZELTİLMİŞ hâli var. Düzeltme kaynağın her bilgisini, isteğini ve "
        "koşulunu korumalıydı; yalnız üslup değişebilirdi. Üç adımda çalış ve her adımı yanıtta yaz.\n"
        "1. Envanter: kaynaktaki her bilgi birimini ayrı bir madde olarak yaz: her istek, talimat, söz ve kural (kim, "
        "neyi, ne zaman, hangi koşulda yapacak); her koşul ve istisna; her kapsam ve nicelik sözü; her sayı, tarih, ad "
        "ve yer; her sav ve sonuç.\n"
        "2. Eşleme: her madde için düzeltilmiş metindeki karşılığını aynen alıntıla ve durumunu yaz: \"ayni\", "
        "\"farkli\" ya da \"yok\".\n"
        "3. Ekleme: düzeltilmiş metni cümle cümle oku; kaynakta karşılığı olmayan somut bir ayrıntı, istek ya da "
        "koşul varsa yaz.\n" + YAZAR_NOTU + ENVANTER_TANIM +
        "Yanıt olarak yalnız şu biçimde JSON ver, başka bir şey yazma:\n"
        '{"envanter": [{"kaynakta": "...", "duzeltmede": "...", "durum": "ayni", "agir": false, "aciklama": ""}], '
        '"eklenen": [{"duzeltmede": "...", "agir": true, "aciklama": "..."}]}\n'
        "\"ayni\" maddelerde \"agir\" false ve açıklama boş olsun.\n\n"
        f"KAYNAK:\n{kaynak.strip()}\n\nDÜZELTİLMİŞ:\n{sonuc.strip()}\n")


BILGI_TURLERI = ("istek", "kosul", "kapsam", "bilgi", "sav", "ayrinti")
SUS_TURLERI = ("duygu", "nezaket", "vurgu", "sus")


def tur_istem(kaynak, sonuc):
    """Envanter, ama her farka tür yazılır; ağırlık türden gelir (Claude, okura etkiyi sorunca değişikliklerin çoğunu
    hafif sayıyordu). Onarıma yalnız bilgi türleri gider; duygu, nezaket, vurgu ve süs sözlerinin düşmesi gitmez."""
    return (
        "Aşağıda bir KAYNAK metin ve onun DÜZELTİLMİŞ hâli var. Düzeltme kaynağın her bilgisini, isteğini ve "
        "koşulunu korumalıydı; yalnız üslup değişebilirdi. Üç adımda çalış ve her adımı yanıtta yaz.\n"
        "1. Envanter: kaynaktaki her bilgi birimini ayrı bir madde olarak yaz: her istek, talimat, söz ve kural (kim, "
        "neyi, ne zaman, hangi koşulda yapacak); her koşul ve istisna; her kapsam ve nicelik sözü; her sayı, tarih, ad "
        "ve yer; her sav, neden ve sonuç.\n"
        "2. Eşleme: her madde için düzeltilmiş metindeki karşılığını aynen alıntıla ve durumunu yaz: \"ayni\", "
        "\"farkli\" ya da \"yok\".\n"
        "3. Ekleme: düzeltilmiş metni cümle cümle oku; kaynakta karşılığı olmayan somut bir ayrıntı, istek, koşul ya "
        "da sav varsa yaz.\n"
        "Her \"farkli\", \"yok\" ve ekleme için türünü yaz:\n"
        "- istek: bir istek, talimat, söz, kural ya da zorunluluk değişti, düştü, eklendi; bir istek düz söze ya da "
        "düz söz isteğe döndü; zorunluluk olanağa döndü ya da tersi.\n"
        "- kosul: bir koşul, süre, istisna ya da olumsuzluk eklendi, düştü ya da değişti.\n"
        "- kapsam: \"tamamı, yalnız, başlıca, en az, yaklaşık, bazı, her\" gibi bir kapsam ya da nicelik sözü "
        "değişti ya da düştü; sayılmamış bir çokluk sayıya döndü.\n"
        "- bilgi: bir sayı, tarih, saat, ad, yer, kurum ya da değişimin yönü değişti ya da düştü.\n"
        "- sav: bir sav, neden, sonuç ya da ihtiyat sözü (\"olabilir\", \"görünüyor\") değişti, düştü ya da eklendi.\n"
        "- ayrinti: kaynakta olmayan somut bir ayrıntı eklendi (tarih, iletişim yolu, sıra, gerekçe, biçim, yer, kişi, "
        "olay).\n"
        "- duygu, nezaket, vurgu, sus: bir duygu sözü, nezaket ya da teşekkür sözü, vurgu sözü (\"küçük\", "
        "\"özellikle\") ya da bilgi taşımayan bir süs cümlesi düştü, eklendi ya da değişti.\n"
        "Aynı şeyi başka sözcüklerle söylemek fark değildir.\n" + YAZAR_NOTU +
        "Yanıt olarak yalnız şu biçimde JSON ver, başka bir şey yazma:\n"
        '{"envanter": [{"kaynakta": "...", "duzeltmede": "...", "durum": "ayni", "tur": "", "aciklama": ""}], '
        '"eklenen": [{"duzeltmede": "...", "tur": "ayrinti", "aciklama": "..."}]}\n'
        "\"ayni\" maddelerde tür ve açıklama boş olsun.\n\n"
        f"KAYNAK:\n{kaynak.strip()}\n\nDÜZELTİLMİŞ:\n{sonuc.strip()}\n")


def envanter_coz(yanit, yalniz_bilgi=False):
    """Envanter yanıtından Rapor: "yok" eksik, "farkli" değişen, ekleme eklenen olur; "ayni" atılır.
    yalniz_bilgi: tür yazılmış ögelerden duygu, nezaket, vurgu ve süs türleri atılır (bilinmeyen tür kalır)."""
    m = re.search(r"\{.*\}", yanit or "", re.S)
    if not m:
        return Rapor(hata="JSON yok")
    try:
        d = json.loads(m.group(0))
    except ValueError as e:
        return Rapor(hata=f"JSON bozuk: {e}")
    if not isinstance(d, dict) or not isinstance(d.get("envanter"), list):
        return Rapor(hata="envanter listesi yok")
    if not isinstance(d.get("eklenen"), list):
        return Rapor(hata="eklenen listesi yok")
    if any(not isinstance(oge, dict) or not isinstance(oge.get("kaynakta"), str)
           or not isinstance(oge.get("durum"), str) or oge["durum"].lower() not in ("ayni", "farkli", "yok")
           for oge in d["envanter"]):
        return Rapor(hata="geçersiz envanter ögesi")
    if any(not isinstance(oge, dict) or not isinstance(oge.get("duzeltmede"), str) for oge in d["eklenen"]):
        return Rapor(hata="geçersiz eklenen ögesi")
    r = Rapor()
    for kaynak_liste, oge in [("envanter", x) for x in d["envanter"]] + [("eklenen", x) for x in d["eklenen"]]:
        if yalniz_bilgi and str(oge.get("tur", "")).lower() in SUS_TURLERI:
            continue
        durum = str(oge.get("durum", "")).lower()
        if kaynak_liste == "eklenen":
            r.eklenen.append(dict(duzeltmede=oge.get("duzeltmede", ""), aciklama=oge.get("aciklama", "")))
        elif durum == "yok":
            r.eksik.append(dict(kaynakta=oge.get("kaynakta", ""), aciklama=oge.get("aciklama", "")))
        elif durum != "ayni":
            r.degisen.append(dict(kaynakta=oge.get("kaynakta", ""), duzeltmede=oge.get("duzeltmede", ""),
                                  aciklama=oge.get("aciklama", "")))
    return r


def coz(yanit, tam=False):
    """Model yanıtından Rapor; JSON bulunamazsa hata alanı dolar ve sorun yok sayılmaz.
    tam: üç listenin üçü de yanıtta olmalı ({} ya da başka bir nesne temiz sayılmaz)."""
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


ISTEMLER = {False: istem, True: siki_istem, "siki": siki_istem, "olgu": olgu_istem, "hedef": hedef_istem,
            "envanter": envanter_istem, "tur": tur_istem}


def denetle(kaynak, sonuc, model, siki=False):
    """model: istem alır, metin döner. siki: anlam onarım turunun istemi (True ya da "siki", "olgu", "hedef",
    "envanter", "tur")."""
    if siki in ("envanter", "tur"):
        return envanter_coz(model(ISTEMLER[siki](kaynak, sonuc)), yalniz_bilgi=siki == "tur")
    return coz(model(ISTEMLER[siki](kaynak, sonuc)), tam=True)
