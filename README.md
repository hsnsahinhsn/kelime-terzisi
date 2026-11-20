# Kelime Terzisi

Kelime Terzisi, yapay zekâ ajanlarının yazdığı Türkçedeki yapay kalıpları bulur ve düzeltir. Bu kalıplara "AI slop" da denir: çeviri kokan cümleler, şişirilmiş anlatım, her cümleyi aynı ekle bitirmek, gereksiz uzun tire.

Araç iki işi yapar:

- Ajan Türkçe yazarken bir yazım kartı ve bir kanca onu bu kalıplardan uzak tutar.
- Yazılmış bir metni denetler ve anlamını koruyarak yeniden yazar.

## Neler var

1. Denetçi: 98 kural, 13 tür. Bulgular üç sınıftadır: yapay zekâ izi, yazım (TDK) ve üslup.
2. Düzeltici: insan yazısı örneklerle ilk yazım, bilgi denetimi, bir okurun yapay bulduğu yerlerin yeniden yazımı, sonra anlam onarımı. Claude Sonnet ve Opus kullanır.
3. Anlam kilidi: düzeltilmiş metinde değişen sayıyı, adı, olumsuzluğu, yönü, alıntıyı ve ihtiyat sözünü bulur.
4. Claude Code için beceri (`skills/kelime-terzisi/`), yazım kartı (`terzi/kart.md`) ve yazım kancası (`hooks/`).

## Ölçüm

Düzeltici, geliştirmede hiç görülmemiş 75 görevde sınandı. Görevleri üç yapay zekâ modeli yazdı; düzeltmeleri iki kör yapay zekâ hakemi puanladı.

- Doğallıkta yalın istemi ("yapay zekâ izlerini gider") ortalama 5,6 puan (yüzde 26) geçti. 12 türün hepsinde öndeydi.
- Üçüncü kör hakem, çiftlerin 75'te 69'unda Kelime Terzisi'nin düzeltmesini seçti.
- Sonradan eklenen anlam adımları, ağır anlam değişikliği olan görevleri yaklaşık 29'dan 16'ya indirdi. Bunun bedeli doğallıkta yaklaşık 1,3 puandır.

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
python3 -m terzi denetle METIN.md --tur TUR
python3 -m terzi duzelt METIN.md --tur TUR > DUZELTILMIS.md
python3 -m terzi anlam METIN.md DUZELTILMIS.md
```

Türler: genel, ajan, rapor, blog, kurumsal, teknik, haber, ansiklopedik, akademik, hukuk, anlati, sosyal, eposta. `--json` makine için çıktı verir. `denetle` ve `duzelt` komutlarında dosya yerine `-` yazılırsa metin standart girdiden okunur.

## Gündelik örnekleri indir

Düzeltici e-posta, ajan yanıtı, sosyal medya ve blog türlerinde insan yazısı örneklere bakar. Bu örnekler gerçek kişilerin Vikipedi tartışma mesajlarıdır, bu yüzden depoda yoktur. Örneksiz çalışınca bu türlerde ilk yazım iki hakem ortalamasında 2,3 puan düşük çıktı.

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
