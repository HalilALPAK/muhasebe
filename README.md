<p align="center"><img src="masaustu/logo.jpg" width="140" alt="Oğul Tarım"></p>

<h1 align="center">Oğul Tarım Muhasebe</h1>

<p align="center">Müşteri bazlı satış fişi, tahsilat, cari hesap, bilanço ve WhatsApp ekstresi.<br>
Windows programı ve Android uygulaması internet üzerinden kendiliğinden eşitlenir.</p>

## İndir

| | Dosya | |
|---|---|---|
| 💻 **Windows** | `OgulTarimMuhasebe.exe` | **[İndir](https://github.com/HalilALPAK/muhasebe/releases/latest/download/OgulTarimMuhasebe.exe)** |
| 📱 **Android** | `OgulTarim.apk` | **[İndir](https://github.com/HalilALPAK/muhasebe/releases/latest/download/OgulTarim.apk)** |

Bütün sürümler: [Releases](https://github.com/HalilALPAK/muhasebe/releases)

### Kurulum
- **Windows:** `.exe` dosyasını bir klasöre koyup çalıştırın. Kurulum gerekmez. Kayıtlar exe'nin yanındaki `muhasebe.db` dosyasında tutulur. Windows "kişisel bilgisayarınızı korudu" uyarısı verirse **Ek bilgi → Yine de çalıştır** seçin.
- **Android:** `.apk` dosyasını telefona indirip açın. Gerekirse "bilinmeyen kaynaklardan yükleme" izni verin.
- **Eşitleme:** Sunucu adresi `https://muhasebe.l1bertech.com` (kendi sunucumuz). Program ve uygulamada hazır gelir; iki cihazda da **Sunucu** ayarına aynı anahtarı girin. Program ilk eşitlemede bilgisayardaki mevcut kayıtların hepsini sunucuya yükler.
- **Eski veritabanları:** Program açılınca masaüstünü tarar. Bu programa ait başka bir `.db` bulursa (örneğin `Desktop\muhasebe.db`) kayıtlarını aktarmayı ve sunucuya göndermeyi önerir. Bulunan dosyaya dokunulmaz.

## Neler yapar

- **Ana ekran:** logo ile **FİŞ** ve **CARİ** düğmeleri.
- **FİŞ:**
  - Müşteri adı yazdıkça öneri gelir; ekranda yalnızca seçilen müşterinin hesabı görünür.
  - Satış fişi: ürün önerisi ve son satış fiyatı kendiliğinden gelir. Tarih kutusuna rakam yazınca noktalar eklenir, fiş numarası otomatik verilir; geçmiş tarihli fiş de girilebilir.
  - Tahsilat, fiş düzeltme ve silme.
  - **Son girilen işlemler** listesi: deftere nerede kaldığınız görünür.
- **CARİ:** bütün müşteriler ve borçları; müşteriye tıklayınca bütün işlemleri.
- **Yıllara göre çalışma:** önceki yıldan kalan borç yeni yıla devreder; yıl değişince program kendisi yeni yıla geçer.
- **Bilanço:** tarih aralığına göre ciro, tahsilat, gider, net kasa, ürün ve müşteri istatistikleri, grafik.
- **Ekstre:** logolu görsel ve PDF; WhatsApp'tan gönderilir.
- **Excel:** dışa aktarma, Excel'den eski satışları alma, boş şablon.
- **Çevrimdışı çalışma:** internet yokken her şey çalışır; değişiklikler bağlantı gelince gönderilir.

## Klasörler

| Klasör | İçerik |
|---|---|
| [`masaustu/`](masaustu) | Windows programı (Python / Tkinter). `derle.bat` ile `.exe` yapılır. |
| [`mobil/`](mobil) | Android uygulaması (Flutter). `flutter build apk --release` |
| [`sunucu/`](sunucu) | Eşitleme sunucusu (kendi sunucumuzda Node.js + SQLite; Cloudflare Workers + D1'de de çalışır) |
| [`docs/SUNUCU.md`](docs/SUNUCU.md) | **API, saklanan veriler, güvenlik, eşitleme kuralları, kurulum ve test raporu** |

## Gizlilik

Bu depo herkese açıktır ve içinde **hiçbir müşteri verisi bulunmaz**. Veritabanı, Excel, PDF ve yedekler `.gitignore` ile dışarıda tutulur. Sunucu anahtarı koda yazılmaz.

Sunucuda hangi verilerin durduğu [docs/SUNUCU.md](docs/SUNUCU.md#2-sunucuda-saklanan-veriler) belgesinde yazılı.

## Geliştirme

```bash
# Windows programı
cd masaustu && pip install -r requirements.txt && python muhasebe.py
derle.bat                                   # ..\dist\OgulTarimMuhasebe.exe

# Android uygulaması
cd mobil && flutter pub get && flutter test && flutter build apk --release

# Sunucu (yerel deneme)
cd sunucu && npm install
npx wrangler d1 execute ogul-tarim-muhasebe --local --file schema.sql
npx wrangler dev --var API_ANAHTARI:deneme
```
