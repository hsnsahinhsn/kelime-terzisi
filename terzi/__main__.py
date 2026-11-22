"""Komut satırı: python3 -m terzi denetle|duzelt|yazim|anlam|istem|havuz|kart|kurallar (ayrıntı: python3 -m terzi -h)."""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from subprocess import TimeoutExpired

from . import SURUM, akis, havuz, model
from .denetci import denetle, kurallar, yazdir
from .kural import TURLER


def _oku(yol):
    return sys.stdin.read() if yol == "-" else Path(yol).read_text(encoding="utf-8")


def _havuz_uyar(tur):
    if tur in akis.GUNDELIK and akis.gundelik_havuz() is None:
        print("Gündelik örnekleri indirmek için `python3 -m terzi havuz` komutunu çalıştırın.", file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser(prog="terzi", description="Kelime Terzisi: Türkçe metinde yapay zekâ izi denetçisi.")
    p.add_argument("--surum", action="version", version=SURUM)
    alt = p.add_subparsers(dest="komut", required=True)
    d = alt.add_parser("denetle", help="metni denetle")
    d.add_argument("metin", help="dosya yolu ya da - (standart girdi)")
    d.add_argument("--tur", default="genel", choices=sorted(TURLER))
    d.add_argument("--json", action="store_true")
    d.add_argument("--en-cok", type=int, default=None, help="her sınıfta en çok bu kadar bulgu")
    d.add_argument("--yalniz", default="", help="düzeyler, virgülle: guclu,orta")
    d.add_argument("--kapat", default="", help="kapatılacak kural kimlikleri, virgülle")
    d.add_argument("--yol", default="karma", choices=["dar", "zeyrek", "karma"])
    dz = alt.add_parser("duzelt", help="Claude ile metni düzelt ve bilgiyi denetle")
    dz.add_argument("metin", help="dosya yolu ya da - (standart girdi)")
    dz.add_argument("--tur", required=True, choices=sorted(TURLER))
    dz.add_argument("--anlam", default=akis.ANLAM_VARSAYILAN, choices=akis.ANLAM_KIPLERI)
    dz.add_argument("--json", action="store_true")
    yz = alt.add_parser("yazim", help="yazmadan önce oku: türün insan yazısı örnekleri ve uydurma yasağı")
    yz.add_argument("--tur", required=True, choices=sorted(TURLER))
    yz.add_argument("--konu", default="", help="görevin kısa özeti; örnek seçimi buna bağlıdır")
    h = alt.add_parser("havuz", help="Vikipedi arşivlerini indir ve gündelik örnek havuzlarını kur")
    h.add_argument("--kok", type=Path, metavar="DIR", help="ham arşivlerin ve havuzların kayıt klasörü")
    an = alt.add_parser("anlam", help="kaynak ile düzeltilmiş metni anlam kilidiyle karşılaştır")
    an.add_argument("kaynak")
    an.add_argument("sonuc")
    an.add_argument("--json", action="store_true")
    alt.add_parser("kart", help="kısa yazım kartını yazdır")
    i = alt.add_parser("istem", help="metin için ölçülen düzeltme istemini yazdır (bulgular, kart, tür notu)")
    i.add_argument("metin", help="dosya yolu ya da - (standart girdi)")
    i.add_argument("--tur", default="genel", choices=sorted(TURLER))
    i.add_argument("--v11", action="store_true", help="v1.1 akışının insan örnekli ilk istemini yazdır")
    k = alt.add_parser("kurallar", help="kuralları listele")
    k.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    if a.komut == "anlam":
        from .anlam import main as anlam_main
        return anlam_main([a.kaynak, a.sonuc] + (["--json"] if a.json else []))
    if a.komut == "yazim":
        from .yazim import yazim_istemi
        try:
            metin = yazim_istemi(a.tur, a.konu)
        except (OSError, ValueError, akis.AkisHatasi) as e:  # ValueError: bozuk UTF-8 ya da JSON
            print(f"terzi: {e}", file=sys.stderr)
            return 1
        kok = akis.gundelik_havuz()
        if metin:
            print(metin)
        elif a.tur in akis.GUNDELIK and (kok is None or not (kok / f"{a.tur}.jsonl").is_file()):
            print(f"terzi: {a.tur} örnekleri yok; `python3 -m terzi havuz` komutunu çalıştırın.", file=sys.stderr)
        else:
            print(f"terzi: {a.tur} türünde insan örneği yok; metni örneksiz yaz.", file=sys.stderr)
        return 0
    if a.komut == "kart":
        from .duzeltici import kart
        print(kart())
        return 0
    if a.komut == "havuz":
        try:
            kok = a.kok.expanduser() if a.kok else havuz.varsayilan_kok()
            havuz.indir(kok)
            sayilar = havuz.kur(havuz.bol(kok / "ham"), kok / "havuz")
        except (OSError, RuntimeError, ValueError) as e:
            print(f"terzi: {e}", file=sys.stderr)
            return 1
        print(", ".join(f"{tur} {sayi}" for tur, sayi in sorted(sayilar.items())))
        print("Metinler CC BY-SA 4.0 lisanslıdır. Yazarlar sayfa geçmişlerinde yer alır. "
              "Arşiv dosyaları bu bilgisayarda kalır. "
              "`duzelt` komutu, seçtiği birkaç kısa örneği Claude'a gönderdiği isteme ekler. "
              "Dosyaları Git deposuna eklemeyin ve paylaşmayın.")
        return 0
    if a.komut == "istem":
        from .duzeltici import istem
        metin = _oku(a.metin)
        if a.v11:
            _havuz_uyar(a.tur)
            sys.stdout.write(akis.ilk_istem(metin, a.tur, akis.duzeltme_ornekleri(metin, a.tur)))
        else:
            print(istem(metin, a.tur, denetle(metin, a.tur)))
        return 0
    if a.komut == "duzelt":
        _havuz_uyar(a.tur)
        try:
            yazar, sonnet = model.claude(model.OPUS), model.claude(model.SONNET)
            sonuc = akis.duzelt(_oku(a.metin), a.tur, yazar, sonnet, sonnet, anlam=a.anlam, **akis.URUN_AKISI)
        except (OSError, TimeoutExpired, akis.AkisHatasi, model.ModelHatasi) as e:
            print(f"terzi: {e}", file=sys.stderr)
            return 1
        kayit = dict(asdict(sonuc), modeller=dict(yazar=model.OPUS, okur=model.SONNET, denetci=model.SONNET), effort=model.EFOR)
        print(json.dumps(kayit, ensure_ascii=False, indent=1) if a.json else sonuc.metin)
        return 0
    if a.komut == "kurallar":
        ks = kurallar()
        if a.json:
            print(json.dumps([{x: getattr(r, x) for x in ("kimlik", "ad", "grup", "sinif", "duzey", "agirlik",
                                                          "turler", "haric_turler", "kaynak")} for r in ks],
                             ensure_ascii=False, indent=1))
        else:
            for r in ks:
                print(f"{r.kimlik}\t{r.sinif}\t{r.duzey}\t{r.ad}")
        return 0
    rapor = denetle(_oku(a.metin), a.tur, yol=a.yol, kapali=set(filter(None, a.kapat.split(","))))
    yalniz = set(filter(None, a.yalniz.split(","))) or None
    if a.json:
        print(json.dumps(rapor.sozluk(), ensure_ascii=False, indent=1))
    else:
        print(yazdir(rapor, a.en_cok, yalniz))
    return 0


if __name__ == "__main__":
    sys.exit(main())
