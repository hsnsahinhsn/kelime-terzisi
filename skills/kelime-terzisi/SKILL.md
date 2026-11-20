---
name: kelime-terzisi
description: Türkçe metin yazarken ya da yazılmış bir Türkçe metni düzeltirken kullan. Yapay zekâ izlerini (tekdüze -mektedir sonları, şişirme sözler, çeviri kalıpları, şablon kapanış, uzun tire) denetçiyle bulur ve anlamı koruyarak düzeltir.
---

# Kelime Terzisi

Türkçe bir metin yazacaksan aşağıdaki kartı uygula. Bitmiş bir metni düzelteceksen "Düzeltme akışı" bölümünü izle.

Türkçe yazarken (Kelime Terzisi kartı)
1. Cümle sonlarını çeşitlendir. Art arda -mektedir, -dır, -mıştır dizme. Türün doğal zamanını kullan: haberde -dı, anlatıda -dı ya da -mış, konuşur gibi yazarken -iyor.
2. Cümle uzunluğunu değiştir. Uzun bir cümleden sonra kısa bir cümle gelebilir. Her paragrafı aynı kalıpla kurma.
3. Cümleleri "Ayrıca", "Bunun yanı sıra", "Öte yandan", "Sonuç olarak" ile açmayı alışkanlık yapma.
4. Şişirme sözleri at: önemli bir rol oynamak, kritik, kapsamlı, dönüm noktası, yadsınamaz, âdeta, geniş bir yelpaze, belirgin biçimde. Değer yargısı yerine bilgiyi ver.
5. Çeviri kalıplarından kaçın: "-e sahip olmak", gereksiz "tarafından", "bir ... olarak", "bu da ... anlamına gelir", "X değil, Y".
6. Kapanışta özet, ders ya da iyimser genelleme ekleme. Son cümle de bilgi taşısın.
7. Uzun tire (—) kullanma; ara sözü virgülle ya da ayrı cümleyle ver. Kalın yazıyı ve emojiyi süs için kullanma.
8. Üçlü listeyi alışkanlık yapma; öğe sayısı malzemeye uysun.
9. Somut ol. Bilmediğin ayrıntıyı uydurma; elindeki bilgiyle yetin.
10. TDK yazımına uy: her şey, bir şey, birçok, ya da; ondalıkta virgül (3,5); "hâlâ" ile "hala" farklıdır.

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
