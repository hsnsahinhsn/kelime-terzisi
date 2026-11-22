"""Claude anlam döngüsü (v1.3, 22.11.2026): bitmiş düzeltmeyi kaynağa karşı Opus denetler, yalnız ağır (MAJOR)
bulgular Opus'la en küçük biçimde yamanır; üç tur. Ürünün Codex'siz anlam güvencesi.

Geliştirme ölçümü (aynı 36 taslak, GPT hakemi, üç kör GPT anlam denetimi; ~/.cache/kt-betik/claude_dongu.py k kolu,
iki okur turundan sonra): yalından %42,3 daha doğal [+7,33, +17,81 puan], kör ağır bulgu 22, yalın 22.
- Denetçi istemi (DENETIM): GPT'nin anlam denetim görevinin tek metinlik hâli, katı ("emin değilsen MAJOR") ve GPT'nin
  başka taslaklarda bulduğu gerçek örnekler (ornekler/anlam_denetim.json, olcum/anlam_ornek_kur.py). Örneksiz istemde
  Opus GPT'nin 35 ağır bulgusunun hiçbirini ağır demedi; örneklerle 24'ünü.
- Yamacı istemi (YAMA): türün insan örnekleri, en küçük yama; zararsız bulgu kanıtla atlanabilir ama koşul, rica
  gücü, kişi ya da sav, kapsam, sayı ve ad değişimi asla (Codex incelemesi 22.11.2026: eski yamacının 130 yamasının
  59'u gereksiz ya da uzundu). Atlamasız yamacı anlamda iyi ama doğallık %20,6; serbest atlama %48,9 ama ağır 27/17.
"""
import json
import re
from pathlib import Path

PAKET = Path(__file__).resolve().parent
TUR_SAYISI = 3

# Üç %s: örnek bloğu, kaynak, düzeltme. Geliştirmedeki claude_denet_tara.IST3 ile bayt bayt aynı.
DENETIM = """Find meaning changes in an edited text, a style edit of its source text. The edit must keep every fact, request and condition of its source. Meaning only, not style, word choice or length.

A meaning change is: a fact dropped or changed (number, name, date, place, direction of change); an unconditional request or statement made conditional, or a condition dropped; a scope word dropped or changed ("all", "only", "main", "at least", "about"); hedging dropped or added ("may", "about"); a new concrete detail not in the source (date, channel, order, reason, form, place, person, event). Equivalent rewording is not a change. Mark each change MAJOR if it changes what a reader would do or believe, else MINOR.

Be as strict as the examples below: a request turned into a statement or an instruction, an offer turned into a promise, a question turned into an order, a dropped attribute or qualifier, a changed agent or cause, a changed time or scope are all changes, and usually MAJOR.

%s

When you are unsure between MAJOR and MINOR, mark MAJOR. A dropped qualifier or detail, a reworded claim that no longer says exactly the same thing, or a changed speech act is MAJOR.

ANSWER (English, compact). One line per change, exactly this shape:
ERR <MAJOR|MINOR> | <short verbatim quote from the edit> | <source wording>
If there are no changes, answer: NONE

SOURCE:
%s

EDIT:
%s"""

# str.format alanları: tur, sorunlar, ornekler, kaynak, metin. Geliştirmedeki yama4_istem.txt ile bayt bayt aynı.
YAMA = """Bir Türkçe metni ({tur}) doğal kılmak için yeniden yazdın. Bir denetçi, yeniden yazdığın metinde birkaç yerin kaynağın anlamını değiştirmiş olabileceğini söyledi:
{sorunlar}

Her sorunu tek tek tart. Kimin ne yaptığını, hangi şeyden söz edildiğini ve sözün kime ait olduğunu kaynakla karşılaştır. Örnek genel kurala, olasılık kesin bilgiye ya da yorum nedene dönüşmüşse anlam değişmiştir. Rica, izin, talimat ve söz verme arasındaki fark da anlamdır: "takın" yerine "takabilirsiniz" denmişse eylem artık isteğe bağlıdır.
Anlam korunmuşsa, yalnız söyleyiş farklıysa, o sorunu atla. Gerekçende anlamı koruyan sözü yeniden yazılmış metinden alıntıla; bu söz komşu bir cümlede de olabilir.
Şu durumlarda hiçbir zaman atlama: bir koşul düşmüş, eklenmiş ya da değişmişse; bir rica, istek, izin, talimat ya da söz vermenin biçimi veya gücü değişmişse; bir eylem ya da sav başka birine, başka bir nedene ya da başka bir şeye bağlanmışsa; kapsam daralmış ya da genişlemişse; bir sayı, ad ya da terim değişmişse.
Anlam gerçekten değişmişse yalnız o yeri onar:
- "eski": yeniden yazılmış metinden harfi harfine, noktalama dahil bir alıntı. Metinde tam bir kez geçsin; olabildiğince kısa olsun, bir cümleyi geçmesin.
- "yeni": onun yerine geçecek söz. Önce tek bir ek ya da kelimeyle düzeltmeyi dene; eksik bir koşul ya da sav için gerekirse kısa bir cümle ekle. Cümlenin geri kalanını, ritmini ve kelime seçimini koru; yamanın getirdiği tekrarı çıkar. Kaynaktaki anlamı tam taşısın: istek ya da zorunluluğun gücü, koşul, kapsam, sayı, ad ve sav kaynaktaki gibi olsun.
- Yeni söz metnin türüne, çevredeki cümlelere ve aşağıdaki insan yazısı örneklerine uysun. Kaynağın söyleyişini ve kalıplarını geri getirme; kitabi kelime yerine insanın konuşurken seçeceği kelimeyi seç. Terimi, madde adını ve sayı birimini gerektiğinde kaynaktaki gibi kullan.
Yanıt olarak yalnız şu JSON'u ver: {{"atlananlar": [{{"sorun": 2, "neden": "...", "alinti": "..."}}], "yamalar": [{{"sorun": 1, "eski": "...", "yeni": "..."}}]}}

Bu türde insanların yazdığı kısa örnekler. Yalnız üslup içindir; konularını, sözlerini ve bilgilerini alma:
{ornekler}

Kaynak metin:
{kaynak}

Yeniden yazılmış metin:
{metin}
"""
SORUN = ("{n}. Yeniden yazılmışta: «{ed}». Kaynakta: «{sr}». Sorun: okurun yapacağı ya da inanacağı şey değişiyor "
         "(anlam değişikliği).")
BULGU = re.compile(r"ERR[ \t]+(MAJOR|MINOR)[ \t]*\|[ \t]*(.+?)[ \t]*\|[ \t]*(.+?)[ \t]*$")


class DonguHatasi(RuntimeError):
    pass


def ornek_blogu():
    """Denetçi örnekleri, geliştirmedeki ornek_blok biçiminde."""
    d = json.loads((PAKET / "ornekler" / "anlam_denetim.json").read_text(encoding="utf-8"))
    return ("MAJOR changes a strict checker found in other texts (edit | source):\n"
            + "\n".join(f"ERR MAJOR | {e} | {s}" for e, s in d["major"])
            + "\n\nMINOR changes from other texts:\n" + "\n".join(f"ERR MINOR | {e} | {s}" for e, s in d["minor"]))


def denetim_istemi(kaynak, metin):
    return DENETIM % (ornek_blogu(), kaynak.strip(), metin.strip())


def bulgular(ham):
    """Denetçi yanıtındaki ERR satırları: (ağırlık, düzeltmedeki söz, kaynaktaki söz). Her satır ayrı çözülür: yarım
    kalan bir satır sonraki satırı alıntı olarak yutmaz (Codex incelemesi, 22.11.2026)."""
    out = []
    for satir in (ham or "").splitlines():
        m = BULGU.search(satir)
        if m:
            out.append((m.group(1), m.group(2).strip("“”\"` "), m.group(3).strip("“”\"` ")))
    return out


def denetle(cagir, kaynak, metin):
    """Denetim yanıtı ya ERR satırı ya NONE içermeli; ikisi de yoksa bir kez yinelenir, sonra hata (düz yazı yanıt
    temiz sayılmasın)."""
    for deneme in range(2):
        ham = cagir(denetim_istemi(kaynak, metin))
        tum = bulgular(ham)
        bozuk = sum(1 for s in (ham or "").splitlines() if re.match(r"\W*ERR\b", s)) != len(tum)
        if not bozuk and (tum or (ham or "").strip().strip("`.* ") == "NONE"):
            return tum
    raise DonguHatasi("denetçi yanıtı iki kez çözülemedi")


def yama_istemi(tur, agir, orn, kaynak, metin):
    """agir: (düzeltmedeki söz, kaynaktaki söz) listesi; orn: türün insan örnekleri."""
    sorunlar = "\n".join(SORUN.format(n=n, ed=ed, sr=sr) for n, (ed, sr) in enumerate(agir, 1))
    ornekler = "\n\n".join(f"Örnek {n}:\n{o.strip()}" for n, o in enumerate(orn, 1)) or "(Bu tür için örnek yok.)"
    return YAMA.format(tur=tur, sorunlar=sorunlar, ornekler=ornekler, kaynak=kaynak.strip(), metin=metin.strip())


def json_liste(ham, anahtar):
    m = re.search(r"\{.*\}", ham or "", re.S)
    if not m:
        raise ValueError("JSON yok")
    d = json.loads(m.group(0))
    if not isinstance(d, dict) or not isinstance(d.get(anahtar), list):
        raise ValueError(f"{anahtar} listesi yok")
    return d[anahtar]


def yama_iste(cagir, istem, n):
    """Yamacı yanıtı: geçerli numaralı yamalar ve atlamalar. Her bulgu ya yamalı ya gerekçeyle atlanmış olmalı; değilse
    bir kez yinelenir, ikinci yanıt yine eksikse eksik bulgular kayda yazılır (Codex incelemesi, 22.11.2026; geliştirme
    koşusunda 122 bulgunun hiçbiri eksik kalmadı). Bozuk JSON iki kez gelirse ValueError."""
    for deneme in range(2):
        ham = cagir(istem)
        try:
            yamalar = json_liste(ham, "yamalar")
        except ValueError:
            if deneme == 1:
                raise
            continue
        try:
            atla = json_liste(ham, "atlananlar")
        except ValueError:
            atla = []
        gecerli = [y for y in yamalar if isinstance(y, dict) and type(y.get("sorun")) is int and 1 <= y["sorun"] <= n
                   and isinstance(y.get("eski"), str) and isinstance(y.get("yeni"), str)]
        atlanan = {a["sorun"] for a in atla if isinstance(a, dict) and type(a.get("sorun")) is int
                   and isinstance(a.get("neden"), str) and a["neden"].strip()}
        eksik = [s for s in range(1, n + 1) if s not in {y["sorun"] for y in gecerli} | atlanan]
        if not eksik or deneme == 1:
            return gecerli, atla, dict(gecersiz=len(yamalar) - len(gecerli), eksik=eksik)


def _gecis(metin, eski):
    """Örtüşenler dahil kaç kez geçtiği ("ha ha", "ha ha ha" içinde iki kez)."""
    n, i = 0, metin.find(eski)
    while i != -1:
        n += 1
        i = metin.find(eski, i + 1)
    return n


def yama_uygula(metin, yamalar):
    """Her yama özgün metne göre çözülür: eski tam bir kez geçmeli ve başka bir yamayla örtüşmemeli; yoksa atlanır
    (Codex plan incelemesi, 21.11.2026). Yamalar sondan başa uygulanır. Uygulanan ve atlanan listeleri döner."""
    yerler, atlanan = [], []
    for y in yamalar:
        eski, yeni = (y.get("eski"), y.get("yeni")) if isinstance(y, dict) else (None, None)
        if not isinstance(eski, str) or not isinstance(yeni, str) or not eski.strip():
            atlanan.append(dict(yama=y, neden="biçim"))
        elif _gecis(metin, eski) != 1:
            atlanan.append(dict(yama=y, neden=f"metinde {_gecis(metin, eski)} kez"))
        elif eski == yeni:
            atlanan.append(dict(yama=y, neden="değişiklik yok"))
        else:
            bas = metin.index(eski)
            if any(bas < s and b < bas + len(eski) for b, s, _ in yerler):
                atlanan.append(dict(yama=y, neden="örtüşme"))
            else:
                yerler.append((bas, bas + len(eski), y))
    for bas, son, y in sorted(yerler, key=lambda x: -x[0]):
        metin = metin[:bas] + y["yeni"] + metin[son:]
    return metin, [y for _, _, y in sorted(yerler, key=lambda x: x[0])], atlanan


def calistir(kaynak, metin, tur, cagir, orn, tur_sayisi=TUR_SAYISI):
    """Her tur: denetim, ağır bulgu varsa yama. Her tur bir öncekinin çıktısını denetler (bulgu çıkmasa da; geliştirme
    ölçümü hep üç tur çalıştı). cagir: Opus (denetçi ve yamacı). Dönüş: (metin, tur kayıtları)."""
    kayitlar = []
    for tur_no in range(1, tur_sayisi + 1):
        once = metin
        tum = denetle(cagir, kaynak, once)
        agir = [(ed, sr) for a, ed, sr in tum if a == "MAJOR"]
        yamalar, uygulanan, atlanan, atla, hesap = [], [], [], None, None
        if agir:
            yamalar, atla, hesap = yama_iste(cagir, yama_istemi(tur, agir, orn, kaynak, once), len(agir))
            metin, uygulanan, atlanan = yama_uygula(once, yamalar)
            metin = metin.strip() + "\n"
            if 2 * len(metin.split()) < len(once.split()):
                raise DonguHatasi(f"yamalı metin çok kısa ({len(metin.split())} kelime)")
        kayitlar.append(dict(tur=tur_no, bulgular=[list(b) for b in tum], agir=len(agir), yamalar=yamalar,
                             uygulanan=len(uygulanan), atlanan=atlanan, atla_gerekce=atla,
                             **({} if not hesap or not (hesap["gecersiz"] or hesap["eksik"]) else dict(hesap=hesap))))
    return metin, kayitlar
