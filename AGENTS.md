# Türkçe yazım (Kelime Terzisi)

Bu depoda ya da bu araçla Türkçe bir metin yazmadan önce türün insan örneklerini al ve çıktıdaki kurala uy:

```sh
python3 -m terzi yazim --tur TUR --konu "görevin kısa özeti"
```

Türkçe bir metni bitirince denetle ve yalnız bulunan yerleri düzelt:

```sh
python3 -m terzi denetle METIN.md --tur TUR
python3 -m terzi anlam KAYNAK.md DUZELTILMIS.md
```

Ayrıntılı akış: `skills/kelime-terzisi/SKILL.md`.
