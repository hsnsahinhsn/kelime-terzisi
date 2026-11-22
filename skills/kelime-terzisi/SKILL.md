---
name: kelime-terzisi
description: Türkçe metin yazmadan önce ya da yazılmış bir Türkçe metni düzeltirken kullan. Yazmadan önce türün insan yazısı örneklerini ve uydurma yasağını verir. Yazılmış metindeki yapay zekâ izlerini (tekdüze -mektedir sonları, şişirme sözler, çeviri kalıpları, şablon kapanış, uzun tire) denetçiyle bulur ve anlamı koruyarak düzeltir.
---

# Kelime Terzisi

Türkçe bir metin yazacaksan önce "Yazmadan önce" bölümünü izle. Bitmiş bir metni düzelteceksen "Düzeltme akışı" bölümünü izle.

## Yazmadan önce

Metnin türünü seç ve şu komutu çalıştır. `--konu` için görevi tek cümleyle özetle.

```sh
bash <beceri klasörü>/terzi.sh yazim --tur TUR --konu "görevin kısa özeti"
```

Komut bu türde insanların yazdığı en çok altı kısa örnek ve bir kural verir. Örneklerden cümle kuruluşunu, ritmi ve kelime seçimini al; konularını ve sözlerini alma. Kurala uy: görevde olmayan tarih, son gün, süre, sayı, ad, koşul, onay, söz ya da kural ekleme.

Ölçümde bu adım 50 taslakta doğallığı ortalama 5,5 puan artırdı ve bilgi hatasını artırmadı. Kuralsız örneklerle yazan ajanlar ise bilgi uydurdu. Bu yüzden kuralı atlama.

E-posta, ajan, sosyal ve blog örnekleri bir kez indirilir (aşağıda `havuz`). Komut "insan örneği yok" derse (genel tür) metni örneksiz yaz.

Metni bitirince denetle ve yalnız bulunan yerleri düzelt.

## Denetçi

Komut bu becerinin klasöründedir:

```sh
bash <beceri klasörü>/terzi.sh denetle METIN.md --tur TUR
bash <beceri klasörü>/terzi.sh denetle - --tur TUR < metin.txt
```

Türler: genel, ajan, rapor, blog, kurumsal, teknik, haber, ansiklopedik, akademik, hukuk, anlati, sosyal, eposta. `--json` makine için çıktı verir. Bulgular üç sınıftadır: yapay zekâ izi (puana girer), yazım (TDK) ve üslup (ayar). Güçlü bulgular önce gelir.

## Düzeltme akışı

Claude komut satırı aracı kuruluysa şu komutu çalıştır. Düzeltme birkaç dakika sürer.

```sh
bash <beceri klasörü>/terzi.sh duzelt METIN.md --tur TUR > DUZELTILMIS.md
```

E-posta, ajan, sosyal ve blog türlerinde düzeltici insan örneklerine bakar. Komut "örnekleri indirin" uyarısı verirse bir kez `bash <beceri klasörü>/terzi.sh havuz` çalıştır (Vikipedi arşivlerinden, yaklaşık 2 dakika). `KT_GUNDELIK_HAVUZ` ayarlıysa o klasör kullanılır; klasör yoksa uyarı sürer.

Claude aracı yoksa v1.1 düzeltme istemini al ve metnin tamamını bu istemle yeniden yaz.

```sh
bash <beceri klasörü>/terzi.sh istem METIN.md --tur TUR --v11
```

Sonucu kaynakla karşılaştır. Sayıları, adları, tarihleri, alıntıları, koşulları ve ihtiyat sözlerini koru. Eksilen ya da değişen bilgiyi düzelt. Kaynakta olmayan bilgiyi çıkar.

Sonra en sık kaçan üç farka ayrıca bak (geliştirme ölçümünde kalan ağır anlam hatalarının çoğu bunlardı):
1. Kaynaktaki her istek, talimat ve söz aynı kaldı mı? Koşulsuz bir isteği koşula bağlama ("bildirin" yerine "gerekirse yazın" olmaz).
2. "Tamamı, yalnız, başlıca, çeşitli" gibi kapsam sözleri yerinde mi? Sayılmamış bir çokluğu sayıya çevirme.
3. Kaynakta olmayan küçük bir ayrıntı eklendi mi: iletişim yolu, biçim, olayların sırası, gerekçe? Varsa çıkar.

## Türe göre

- Haber: olayı ilk cümlede ver, -dı ile anlat; "belirtti, vurguladı, ifade etti" döngüsü kurma; alıntılar aynen kalır.
- Akademik ve hukuk: edilgen yapı ve -mektedir bu türlerde yerleşiktir; yalnız yığılmayı ve şişirmeyi düzelt.
- Blog ve sosyal medya: konuşur gibi yaz ama samimiyeti abartma; yazarın emoji alışkanlığını koru; soruyla ya da öğütle kapanma.
- E-posta: selam ve kapanış kalsın; "Umarım bu e-posta sizi iyi bulur" çeviri kalıbıdır.
- Ajan yanıtı: doğrudan cevapla başla; "Harika soru", "Elbette!", sondaki özet, "isterseniz şunu da yaparım" teklifi ve "Umarım yardımcı olur" yok. Bilgiyi etiketli kısa maddelere bölme; liste yalnız adımlar için.
- Teknik: komut, kod, sürüm ve arayüz adları değişmez.
