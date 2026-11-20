"""Türkçe Vikipedi arşivlerinden gündelik örnek havuzlarını kur."""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from tempfile import NamedTemporaryFile

SABIT = "2026-11-19T08:05:30Z"
KLASORLER = (("koy-cesmesi", "Köy çeşmesi"), ("danisma", "Danışma masası/Arşiv"))
TURLER = ("eposta", "ajan", "sosyal", "blog")
YIL = re.compile(r"/(?:Arşiv/)?(?:\w+ )?(20\d\d)\b")
AY = "Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık"
TS = re.compile(rf"(\d{{1,2}})[.:](\d{{2}}), (\d{{1,2}}) ({AY}) (\d{{4}}) \(UTC\)")
BASLIK = re.compile(r"^=+[^=\n]+=+\s*$", re.M)
EN = set("the and to of is you for we are this that with be have not on it".split())
KABA = re.compile(r"\b(salak|aptal|rezil|saçma|yalan|terbiye|hakaret|lan|ahmak|cahil|yobaz)\b", re.I)


def varsayilan_kok():
    onbellek = os.getenv("XDG_CACHE_HOME")
    return (Path(onbellek) if onbellek else Path.home() / ".cache") / "kelime-terzisi"


def _api(**sorgu):
    adres = "https://tr.wikipedia.org/w/api.php?" + urllib.parse.urlencode(dict(sorgu, format="json"))
    baslik = {"User-Agent": "kelime-terzisi (ornek havuzu indirme; dusuk hacim)"}
    istek = urllib.request.Request(adres, headers=baslik)
    for i in range(6):
        try:
            with urllib.request.urlopen(istek, timeout=60) as yanit:
                veri = json.load(yanit)
            if "error" in veri:
                raise RuntimeError(veri["error"]["info"])
            return veri
        except urllib.error.HTTPError as e:
            e.close()
            if e.code != 429:
                raise
            time.sleep(10 * (i + 1))
    raise RuntimeError("429")


def _yaz(yol, satirlar):
    dosya = NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=yol.parent, delete=False)
    gecici = Path(dosya.name)
    try:
        with dosya:
            dosya.writelines(satirlar)
        gecici.replace(yol)
    finally:
        gecici.unlink(missing_ok=True)


def _ham_yol(klasor, baslik):
    return klasor / (baslik.replace("/", "__") + ".txt")


def _icerik(baslik, revizyon):
    try:
        return revizyon["slots"]["main"]["*"]
    except (KeyError, TypeError) as e:
        raise RuntimeError(f"{baslik} sayfasının sürüm içeriğine erişilemiyor.") from e


def indir(kok, api=_api):
    """Arşivleri ham vikimetin olarak indir. Var olan dosyaları yeniden çekme."""
    ilk = True

    def sorgula(devam_et=True, **sorgu):
        nonlocal ilk
        devam = {}
        while True:
            if not ilk:
                time.sleep(2)
            ilk = False
            veri = api(action="query", **sorgu, **devam)
            yield veri.get("query", {})
            if not devam_et or not (devam := veri.get("continue")):
                return

    def surumler(basliklar, devam_et=True, **sorgu):
        sayfalar = {}
        for yanit in sorgula(devam_et, prop="revisions", rvprop="content|timestamp", rvslots="main",
                              titles=basliklar, **sorgu):
            for sayfa in yanit.get("pages", {}).values():
                baslik = sayfa["title"]
                if not sayfalar.get(baslik, {}).get("revisions"):
                    sayfalar[baslik] = sayfa
        return sayfalar

    for klasor, onek in KLASORLER:
        cikti = Path(kok) / "ham" / klasor
        cikti.mkdir(parents=True, exist_ok=True)
        basliklar = []
        for yanit in sorgula(list="allpages", apnamespace=4, apprefix=onek, aplimit=500):
            basliklar.extend(p["title"] for p in yanit.get("allpages", ()))
        secili = [b for b in basliklar if (m := YIL.search(b)) and int(m.group(1)) <= 2021]
        for i in range(0, len(secili), 20):
            yeni = [b for b in secili[i:i + 20] if not _ham_yol(cikti, b).exists()]
            if not yeni:
                continue
            sayfalar = surumler("|".join(yeni))
            for baslik in yeni:
                sayfa = sayfalar.get(baslik, {})
                if "missing" in sayfa:
                    continue
                revizyonlar = sayfa.get("revisions")
                if not revizyonlar:
                    raise RuntimeError(f"Vikipedi, {baslik} sayfası için sürüm döndürmedi.")
                if revizyonlar[0]["timestamp"] > SABIT:
                    # Sabit andaki sürüm: yalnız ilk yanıt (devam, daha eski sürümleri tek tek gezer).
                    eski = surumler(baslik, devam_et=False, rvstart=SABIT, rvdir="older", rvlimit=1)
                    revizyonlar = eski.get(baslik, {}).get("revisions")
                    if not revizyonlar:
                        continue
                _yaz(_ham_yol(cikti, baslik), (_icerik(baslik, revizyonlar[0]),))


def _temizle(t):
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    for _ in range(5):
        t = re.sub(r"\{\{[^{}]*\}\}", " ", t)
    t = re.sub(r"\[\[(?:Dosya|File|Resim|Image|Kategori|Category):[^\]]*\]\]", " ", t, flags=re.I)
    t = re.sub(r"\[\[(?:Kullanıcı|User|Kullanıcı mesaj|User talk|Özel:Katkılar)[^\]]*\]\]", " ", t, flags=re.I)
    t = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[\[([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[(?:https?:)?//\S+ ([^\]]+)\]", r"\1", t)
    t = t.replace("'''", "").replace("''", "")
    t = re.sub(r"^[:*#;]+\s*", "", t, flags=re.M)
    t = re.sub(r"\(\s*mesaj\s*\)|\(\s*katkılar\s*\)|--\s*$|—\s*$", " ", t.strip())
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip(" -—\n")


def bol(ham_kok):
    """İmza saatlerine göre ayır, mesajları temizle ve süz."""
    mesajlar = []
    for klasor, _ in KLASORLER:
        for yol in sorted((Path(ham_kok) / klasor).glob("*.txt")):
            ham = yol.read_text(encoding="utf-8")
            bas = 0
            for m in TS.finditer(ham):
                parca, bas = ham[bas:m.start()], m.end()
                basliklar = list(BASLIK.finditer(parca))
                if basliklar:
                    parca = parca[basliklar[-1].end():]
                yil = int(m.group(5))
                if yil > 2021 or re.search(r"\(WMF\)|message delivery|Int:|translate|MediaWiki|bot\b", parca, re.I):
                    continue
                metin = _temizle(parca)
                kel = metin.split()
                if not 40 <= len(kel) <= 220 or sum(w.lower() in EN for w in kel) / len(kel) > 0.04:
                    continue
                if re.search(r"https?://|www\.|\{\{|\}\}|\||==|__", metin) or not re.search(r"[ıışğİŞĞ]", metin):
                    continue
                mesajlar.append(dict(kaynak=klasor, sayfa=yol.stem, yil=yil, kelime=len(kel), metin=metin))
    return mesajlar


def _sinif(x):
    t = x["metin"]
    bas = t[:40].lower()
    if t.count('"') >= 4 or t.count("“") >= 2 or len(t.split("\n\n")) > 3:
        return None
    if KABA.search(t) or re.search(r"imzasız|tarafından eklenmiştir|!!|[A-ZÇĞİÖŞÜ]{6,}", t):
        return None
    if not 50 <= x["kelime"] <= 160:
        return None
    harf = [c for c in t if c.isalpha()]
    if sum(c in "çğıöşüÇĞİÖŞÜ" for c in harf) / max(1, len(harf)) < 0.03:
        return None
    if re.match(r"(merhaba|selam|sayın|değerli|arkadaşlar|herkese)", bas):
        return "eposta"
    if x["kaynak"] == "danisma":
        return "ajan"
    if t.rstrip().endswith("?"):
        return None
    if re.match(r"(bence|ben de|katılıyorum|evet|hayır|bana göre|bu konuda)", bas):
        return "sosyal"
    return "blog" if x["kelime"] >= 80 else None


def kur(mesajlar, havuz_kok):
    """Mesajları türlerine göre yaz ve her havuzun sayısını döndür."""
    cikti = Path(havuz_kok)
    cikti.mkdir(parents=True, exist_ok=True)
    havuz = {s: [] for s in TURLER}
    for x in mesajlar:
        s = _sinif(x)
        if s:
            havuz[s].append(x)
    for s, v in havuz.items():
        _yaz(cikti / f"{s}.jsonl", (json.dumps(x, ensure_ascii=False) + "\n" for x in v))
    return {s: len(v) for s, v in havuz.items()}
