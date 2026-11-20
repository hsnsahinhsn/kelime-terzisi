# Katkı

1. Depoyu kendi hesabına çatalla (fork) ve kendi dalında çalış.
2. İşin bitince `main` dalına bir çekme isteği (PR) aç. Neyi neden değiştirdiğini kısaca yaz.
3. Testler geçmeli: `python3 -m unittest discover -s tests -t . -q`.
4. Yeni bir kural eklersen en az bir "yakalamalı" ve bir "yakalamamalı" örnek yaz; ikişer örnek daha iyidir. Testler bunları kendiliğinden dener. Kural kaydının biçimi: `terzi/kural.py` ve `terzi/kurallar/*.toml`.
5. Başka bir projeden kural ya da metin alırsan kaynağını kuralın `kaynak` satırına, lisansını `UCUNCU-TARAF.md` dosyasına yaz.
6. Telifli metin, kişisel veri, anahtar ya da parola ekleme.

Bu depo sürümlerin yayınlandığı yerdir. Kabul edilen değişiklik geliştirme deposunda sınanır ve bir sonraki sürümle buraya gelir. Bu yüzden PR'ın kendisi birleştirilmeden kapanabilir; katkın sürüm notunda anılır.
