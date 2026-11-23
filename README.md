# Kelime Terzisi

Kelime Terzisi, yapay zekâ ajanlarının yazdığı Türkçedeki yapay kalıpları bulur ve düzeltir. Bu kalıplara "AI slop" da denir: çeviri kokan cümleler, şişirilmiş anlatım, her cümleyi aynı ekle bitirmek, gereksiz uzun tire.

Araç iki işi yapar:

- Ajan Türkçe bir metin yazmadan önce türün insan yazısı örneklerini ve bir uydurma yasağını görür. Bir kanca yazılan metni denetler.
- Yazılmış bir metni denetler ve anlamını koruyarak yeniden yazar.

## Neler var

1. Denetçi: 98 kural, 13 tür. Bulgular üç sınıftadır: yapay zekâ izi, yazım (TDK) ve üslup.
2. Düzeltici: insan yazısı örneklerle ve anlamı kilitli ilk yazım, bilgi denetimi, bir okurun yapay bulduğu yerlerin yeniden yazımı, anlam onarımı, ikinci bir okur turu, en sonda üç turluk anlam döngüsü. Döngüde Opus anlam değişikliklerini arar ve yalnız ağır olanları en küçük değişiklikle onarır. Claude Sonnet ve Opus kullanır. Taslağın sonunda isteyene yazılmış bir not varsa ("Metin yaklaşık 128 kelime", "tarih eklemedim"), not düzeltmeden önce ayrılır ve ayrıca verilir.
3. Anlam kilidi: düzeltilmiş metinde değişen sayıyı, adı, olumsuzluğu, yönü, alıntıyı ve ihtiyat sözünü bulur.
4. Yazım istemi (`python3 -m terzi yazim`): türün en çok altı insan örneği ve bir uydurma yasağı. Claude Code becerisi (`skills/kelime-terzisi/`) ve `AGENTS.md` ajana bunu yazmadan önce çalıştırmasını söyler.
5. Yazım kancası (`hooks/`): ajanın yazdığı Türkçe dosyayı denetler.

## Ölçüm

Doğallık puanı, kör hakemin metni insan yazısı sayma olasılığıdır (0-100).

Düzeltici (sürüm 1.3), geliştirmede hiç görülmemiş 75 görevde sınandı. Taslaklar üç yapay zekâ modeliyle yazıldı (Claude Opus, Claude Sonnet ve GPT, her biri 25 taslak). Düzeltmeler kör bir GPT hakemiyle puanlandı. Anlam, iki ayrı kör GPT denetimiyle kaynak taslağa karşı denetlendi.

- Doğallıkta yalın istem ("yapay zekâ izlerini gider") ortalama 8,0 puan (yüzde 28) geçildi. %95 aralık 4,8 ile 11,4 puandır. Düzeltici 75 görevin 50'sinde daha yüksek, 12'sinde daha düşük puan aldı.
- Yalnız Claude'un yazdığı 50 taslakta kazanç 4,5 puandır (yüzde 16). GPT taslaklarında kazanç 14,9 puandır; hakem de GPT olduğu için bu sayı ayrı verilir.
- İki kör denetimin toplamında ağır anlam hatası düzelticide 11, yalın istemde 39 bulundu.
- Sınavdan önce iki ölçüt konmuştu: en az yüzde 30 doğallık ve yalından fazla olmayan ağır anlam hatası. Anlam ölçütü tuttu, doğallık ölçütü 0,5 puanla tutmadı.
- Düzeltici metin başına ortalama 5 dakika çalıştı (Claude, xhigh eforla).
- Sürüm 1.4'ün akışı 1.3 ile aynıdır. Tek fark, yazar notunun düzeltmeden önce ayrılmasıdır. Sınavda not iki metinde korunmuştu ve bu metinler çok düşük puan almıştı. Sınavın notlu 9 taslağında yeniden ölçüldü: notu ayrılan bir metnin puanı 5'ten 38'e çıktı. Öbür metinlerdeki farklar düzelticinin her koşuda biraz farklı yazmasından gelir.

Yazım istemi 50 taslakta, aynı görevin yalın istemle yazılmış taslağıyla karşılaştırıldı. İki kör yapay zekâ hakemi puanladı.

- Doğallık ortalama 5,5 puan arttı. 37 taslak iyileşti, 8 taslak kötüleşti.
- Kör bilgi denetiminde ağır hata sayısı artmadı (yalın istemde 7, yazım isteminde 6).
- Kural olmadan verilen örnekler bilgi uydurmayı artırdı (ağır hata 12). Kural bu yüzden istemin parçasıdır.
- Ölçümde haber ve akademik türlerinde altı örnek vardı. Bu depodaki serbest lisanslı örnekler bu iki türde daha azdır (haber 3, akademik 2).
- Rapor ve kurumsal türlerinin örnekleri (Wikimedia Türkiye topluluğunun duyuruları ve toplantı notları, CC BY-SA) yalnız `yazim` komutunda kullanılır. Ölçümde (48 taslak) yazarken doğallığı değiştirmediler ama hafif bilgi hatasını 8'den 2'ye indirdiler; düzelticinin ilk yazımında doğallığı biraz düşürdüler (-1,2, anlamlı değil), bu yüzden düzeltici bu iki türde örneksiz yazar.
- İlk yazımda anlam kilidi: kör denetimde anlam kayması bulguları 53'ten 26'ya indi, doğallık düşmedi (45 taslak).

## Kurulum

Python 3.11 ya da üstü gerekir (3.11 ve 3.14 ile sınandı). Ek paket gerekmez. Düzeltici için Claude Code komut satırı aracı (`claude`) kurulu ve oturum açık olmalıdır. Denetçi ve anlam kilidi ağsız çalışır.

```sh
git clone https://github.com/hsnsahinhsn/kelime-terzisi.git
cd kelime-terzisi
python3 -m terzi --surum
```

Claude Code eklentisi olarak denemek için deponun üst klasöründe `claude --plugin-dir ./kelime-terzisi` çalıştırın.

## Kullanım

```sh
python3 -m terzi yazim --tur TUR --konu "görevin kısa özeti"
python3 -m terzi denetle METIN.md --tur TUR
python3 -m terzi duzelt METIN.md --tur TUR > DUZELTILMIS.md
python3 -m terzi anlam METIN.md DUZELTILMIS.md
```

Türler: genel, ajan, rapor, blog, kurumsal, teknik, haber, ansiklopedik, akademik, hukuk, anlati, sosyal, eposta. `--json` makine için çıktı verir. `denetle` ve `duzelt` komutlarında dosya yerine `-` yazılırsa metin standart girdiden okunur.

## Gündelik örnekleri indir

Düzeltici ve `yazim` komutu e-posta, ajan yanıtı, sosyal medya ve blog türlerinde insan yazısı örneklere bakar. Bu örnekler gerçek kişilerin Vikipedi tartışma mesajlarıdır, bu yüzden depoda yoktur. Örneksiz çalışınca bu türlerde düzelticinin ilk yazımı iki hakem ortalamasında 2,3 puan düşük çıktı.

`python3 -m terzi havuz` komutu bu örnekleri Türkçe Vikipedi'nin tartışma arşivlerinden (2005-2021) çıkarır. Bir kez çalıştırmak yeter, yaklaşık 2 dakika sürer. Sayfalar 19.11.2026 tarihli sürümlerine sabitlenir.

Dosyalar `~/.cache/kelime-terzisi` içine yazılır. `XDG_CACHE_HOME` ayarlıysa komut onun altındaki `kelime-terzisi` klasörünü kullanır. Başka bir klasör için `--kok DIR` verin ve `KT_GUNDELIK_HAVUZ` değerini `DIR/havuz` yapın.

Metinler CC BY-SA 4.0 lisanslıdır. Yazarlar sayfa geçmişlerinde yer alır. Dosyaları bir Git deposuna eklemeyin. `duzelt`, seçtiği birkaç kısa örneği Claude'a giden isteme koyar.

## Testler

```sh
python3 -m unittest discover -s tests -t . -q
```

Testler ağ ve veri olmadan çalışır.

## Lisans

Kod MIT lisanslıdır (`LICENSE`). Başka projelerden uyarlanan kurallar ve kendi lisansıyla gelen örnek metinler `UCUNCU-TARAF.md` dosyasında listelenir.
