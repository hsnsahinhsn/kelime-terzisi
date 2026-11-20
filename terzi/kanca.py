"""Claude Code kancaları: yazarken koruma.

- `yazim` (PostToolUse, Write/Edit/MultiEdit): ajan bir Türkçe metin dosyası yazınca denetler.
  Güçlü bulgu varsa en çok 3 tanesini ajana geri verir. Aynı dosya için bir kez düzeltme
  hakkı verir; ikinci yazımda susar.
- `yanit` (Stop, isteğe bağlı): ajanın son sohbet yanıtını denetler. Güçlü bulgu varsa bir kez
  düzeltme ister (stop_hook_active iken susar).

Kanca hiçbir durumda işi durdurmaz: hata, zaman aşımı ya da Türkçe olmayan metinde sessiz çıkar.
"""
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

UZANTI = {".md", ".markdown", ".txt", ".rst", ".html", ".tex"}
EN_COK = 3
TR_HARF = re.compile(r"[çğışöüÇĞİŞÖÜ]")
TR_SOZ = re.compile(r"\b(?:ve|bir|bu|için|ile|olarak|daha|gibi|değil|çok)\b", re.I)


def turkce_mi(metin):
    harf = sum(ch.isalpha() for ch in metin)
    if harf < 200:
        return False
    return len(TR_HARF.findall(metin)) / harf > 0.015 and len(TR_SOZ.findall(metin)) >= 5


def _durum_yolu(oturum):
    kok = Path(os.environ.get("XDG_STATE_HOME") or Path(tempfile.gettempdir())) / "kelime-terzisi-kanca"
    kok.mkdir(parents=True, exist_ok=True)
    ad = hashlib.sha256((oturum or "yok").encode()).hexdigest()[:16]
    return kok / f"{ad}.json"


def _durum(oturum):
    try:
        return json.loads(_durum_yolu(oturum).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _kaydet(oturum, d):
    try:
        _durum_yolu(oturum).write_text(json.dumps(d), encoding="utf-8")
    except OSError:
        pass


def bulgu_metni(rapor, kaynak):
    guclu = [b for b in rapor.yz if b.duzey == "guclu"][:EN_COK]
    if not guclu:
        return ""
    satir = [f"Kelime Terzisi denetimi ({kaynak}): Türkçe metinde {len(guclu)} güçlü yapay zekâ izi var."]
    for b in guclu:
        yer = f"{b.cumle + 1}. cümle" if b.cumle >= 0 else "metnin geneli"
        alinti = f" «{b.alinti}»" if b.alinti else ""
        satir.append(f"- {yer}:{alinti} {b.mesaj}. Öneri: {b.oneri}")
    satir.append("Bu yerleri bir kez düzelt. Bilgiyi, sayıları ve anlamı koru; yeni bilgi ekleme. "
                 "Düzeltmeden sonra bu denetim tekrar istenmez.")
    return "\n".join(satir)


def yazim(girdi):
    arac = girdi.get("tool_input") or {}
    yol = arac.get("file_path") or arac.get("path")
    if not yol or Path(yol).suffix.lower() not in UZANTI:
        return None
    p = Path(yol)
    if not p.is_file() or p.stat().st_size > 400_000:
        return None
    metin = p.read_text(encoding="utf-8", errors="ignore")
    if not turkce_mi(metin):
        return None
    oturum = girdi.get("session_id", "")
    d = _durum(oturum)
    anahtar = str(p.resolve())
    if d.get(anahtar, 0) >= 1:
        return None  # bu dosya için düzeltme hakkı kullanıldı
    from .denetci import denetle
    rapor = denetle(metin, os.environ.get("KELIME_TERZISI_TUR", "genel"))
    mesaj = bulgu_metni(rapor, p.name)
    if not mesaj:
        return None
    d[anahtar] = d.get(anahtar, 0) + 1
    _kaydet(oturum, d)
    return {"decision": "block", "reason": mesaj}


def son_yanit(transcript):
    """Konuşma kaydından son asistan metnini alır."""
    son = None
    try:
        satirlar = Path(transcript).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for s in reversed(satirlar):
        try:
            d = json.loads(s)
        except ValueError:
            continue
        if d.get("type") != "assistant":
            if d.get("type") == "user" and son is not None:
                break
            continue
        icerik = (d.get("message") or {}).get("content") or []
        parca = [c.get("text", "") for c in icerik if isinstance(c, dict) and c.get("type") == "text"]
        if parca:
            son = "\n".join(parca) + ("\n" + son if son else "")
    return son


def yanit(girdi):
    if girdi.get("stop_hook_active"):
        return None
    metin = son_yanit(girdi.get("transcript_path", ""))
    if not metin or not turkce_mi(metin) or len(metin.split()) < 60:
        return None
    from .denetci import denetle
    mesaj = bulgu_metni(denetle(metin, "ajan"), "son yanıt")
    if not mesaj:
        return None
    return {"decision": "block", "reason": mesaj + " Yanıtını düzeltilmiş hâliyle yeniden ver."}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    kip = argv[0] if argv else "yazim"
    try:
        girdi = json.loads(sys.stdin.read() or "{}")
        cikti = {"yazim": yazim, "yanit": yanit}[kip](girdi)
    except Exception:
        return 0  # kanca işi asla durdurmaz
    if cikti:
        print(json.dumps(cikti, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
