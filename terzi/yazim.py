"""Yazarken koruma (v1.3): ajan Türkçe bir metin yazmadan önce türün insan yazısı örneklerini ve uydurma yasağını görür.

Ölçüm (20.11.2026, 50 taslak, iki kör hakem; olcum/ornek_yaz.py --kilit): yalın taslaktan doğallıkta +5,5 puan, 37 taslak
iyi, 8 kötü. Kör bilgi denetiminde ağır hata 6 (yalın taslakta 7). Kuralsız örnekler ağır hatayı 12'ye çıkardı: örnekler
yazarı insan gibi somut ayrıntı (tarih, son gün, onay, hüküm) uydurmaya itiyor, bu yüzden kural örneklerden ayrılmaz.
Yazım kartı (kart.md) bu akışta yok: v1.0 ölçümünde bilgili taslaklarda doğallığı düşürdü.

Metin ölçülen istemle harfi harfine aynıdır (tests/test_yazim.py denetler). Ölçümde Claude yazarlar istemi sistem
isteminde, GPT görevin başında gördü; ikisi de kazandı.
"""
from . import akis

GIRIS = "Türkçe metin yazarken aşağıdaki insan yazısı örneklerine bak.\n\n"
ORNEK_GIRISI = ("Bu türde insanların yazdığı kısa örnekler. Konularını ve sözlerini alma; yalnız cümle kuruluşunu, "
                "ritmi ve kelime seçimini örnek al. Örneklerdeki yazım hatalarını alma:\n\n")
KILIT = ("Örnekler yalnız üslup içindir; içerik görevden gelir. Görevin vermediği bir tarih, gün, son gün, süre, sayı, "
         "ad, yer, koşul, onay, söz ya da kural ekleme; metin insan yazısı gibi görünsün diye somut ayrıntı uydurma. "
         "Görevdeki her bilgiyi kapsamını değiştirmeden aktar: kim, neyi, ne zaman ve hangi koşulda yapacak, aynen kalsın; "
         "bir bilgiyi daraltma, genişletme ya da başka bir bilgiye bağlama.")


def istem(orn):
    """Örnekler ve uydurma yasağı. Örnek yoksa boş metin: kural tek başına ölçülmedi."""
    if not orn:
        return ""
    ornek = "\n\n".join(f"Örnek {i}:\n{o.strip()}" for i, o in enumerate(orn, 1))
    return (GIRIS + ORNEK_GIRISI + ornek + "\n\n" + KILIT).strip()


def yazim_istemi(tur, konu=""):
    """Türün en çok altı insan örneği; seçim konuya bağlıdır (konu yoksa türe)."""
    return istem(akis.ornekler(konu.strip() or tur, tur))
