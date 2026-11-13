# Sunucu, API ve Saklanan Veriler

Bu belge Oğul Tarım Muhasebe'nin internet üzerinden eşitleme yapısını anlatır: neden böyle kurulduğunu, sunucuda hangi verilerin durduğunu, API'yi ve nasıl test edildiğini.

## 1. Genel yapı

```
 Windows programı (.exe)          Android uygulaması (.apk)
   yerel muhasebe.db                 yerel muhasebe.db
          │   HTTPS + anahtar             │
          └──────────►  Cloudflare  ◄─────┘
                    Workers (sunucu/src/index.js)
                    D1 veritabanı (sunucu/schema.sql)
```

- **Her cihaz kendi verisini yerelde tutar.** İnternet yokken program ve uygulama normal çalışır.
- Yapılan her değişiklik yerelde **"gönderilecek"** diye işaretlenir. İnternet varken birkaç saniye içinde sunucuya gider. Ayrıca her dakika diğer cihazın yaptığı değişikliklere bakılır.
- **Birleştirme kurallarının tamamı sunucudadır.** Cihazlar sunucunun verdiği sonucu uygular, bu yüzden iki cihaz birbirinden ayrışamaz.
- Mevcut `muhasebe.db` dosyasındaki bütün kayıtlar **ilk eşitlemede sunucuya yüklenir.** Geçişten önce `Yedekler` klasörüne otomatik yedek alınır.

### Neden Cloudflare Workers + D1?

| İhtiyaç | Karşılığı |
|---|---|
| Sunucu bakımı olmasın | Workers sunucusuz çalışır; işletim sistemi, güncelleme, yedek disk yok |
| Veri ilişkisel (müşteri → fiş → ürün) | D1, SQLite tabanlıdır; programdaki veritabanıyla aynı mantık |
| Maliyet | Bu işletmenin hacmi ücretsiz planın çok altında kalır (bkz. §7) |
| Güvenli bağlantı | Cloudflare adresleri HTTPS'tir; ayrıca sertifika gerekmez |

## 2. Sunucuda saklanan veriler

Sunucuda yalnızca programda girilen muhasebe kayıtları durur:

| Tablo | Alanlar | Açıklama |
|---|---|---|
| `musteri` | uuid, ad, telefon, notlar | Müşteri kartı |
| `islem` | uuid, musteri_uuid, tur (`SATIŞ`/`TAHSİLAT`), tarih, tutar, aciklama, fis_no, kalemler | Satış fişleri (ürün satırları `kalemler` içinde: ürün, adet, birim fiyat) ve tahsilatlar |
| `gider` | uuid, tarih, kategori, tutar, aciklama | Giderler |
| `esleme` | eski, yeni | İki cihazda aynı isimle açılıp birleştirilen müşteriler |
| `kayit` | zaman, cihaz, gelen, rapor | Eşitleme günlüğü: hangi cihaz (örn. `LAPTOP`, `telefon`), ne zaman, kaç kayıt gönderdi |
| `meta` | surum | Eşitleme sayacı |

Her kayıtta ayrıca şu teknik alanlar bulunur:
- `guncelleme`: son değişikliğin zamanı
- `silindi`: silinen kayıtlar bu işaretle saklanır, böylece eski bir kopyadan geri gelmez
- `surum`: cihazların "bu sürümden sonrasını ver" diye sorduğu sayaç

**Sunucuda olmayanlar:**
- Ekstre görselleri ve PDF'leri (cihazda üretilir)
- Excel dosyaları
- Yerel yedekler
- Sunucu anahtarı (koda yazılmaz; Cloudflare'de gizli değişken olarak durur)
- Konum veya cihaz kimliği gibi bilgiler

Cihaz adı yalnızca kullanıcının ayarlarda yazdığı addır.

## 3. Güvenlik

- **HTTPS:** Bütün trafik şifrelidir. Cloudflare D1 verileri diskte şifreli saklar.
- **Anahtar:** Her istek `Authorization: Bearer <anahtar>` taşır. Anahtar Worker'da `API_ANAHTARI` gizli değişkenidir ve zamanlamaya dayanıklı karşılaştırılır. Anahtarı olmayan hiçbir veriyi okuyamaz veya yazamaz.
- **Anahtar ele geçerse veya telefon kaybolursa:**
  1. `npx wrangler secret put API_ANAHTARI` ile anahtarı değiştirin.
  2. Yeni anahtarı cihazların Sunucu Ayarları'na girin.
- **Depo herkese açıktır** ama içinde müşteri verisi, `.db`, Excel, PDF ve anahtar **yoktur**; bunlar `.gitignore` ile dışarıda tutulur.
- **Girdi doğrulama:** Sunucu gelen her alanı kontrol eder (tarih biçimi, sayı, metin uzunluğu, işlem türü). Bozuk bir istekte hiçbir şey yazılmaz: bir istek ya tamamen işlenir ya hiç işlenmez.

## 4. API

Temel adres, Cloudflare'in verdiği adrestir (`https://ogul-tarim-muhasebe.<hesap>.workers.dev`). `/` dışındaki her istek `Authorization: Bearer <anahtar>` başlığı ister.

### `GET /`
Anahtar istemez; sunucunun ayakta olduğunu gösterir.
```json
{ "uygulama": "ogul_tarim", "api": 1 }
```

### `GET /v1/durum`
Bağlantı testi ve özet.
```json
{ "uygulama": "ogul_tarim", "api": 1, "son_surum": 1790,
  "musteri": 69, "islem": 221, "gider": 3,
  "son_esitleme": { "zaman": 1794611177846, "cihaz": "LAPTOP" } }
```

### `POST /v1/esitle`
Cihaz gönderilecek kayıtlarını yollar, karşılığında son gördüğü sürümden sonra değişen kayıtları alır.

İstek:
```json
{
  "api": 1,
  "cihaz": "telefon",
  "son_surum": 1790,
  "degisiklikler": {
    "musteri": [ { "uuid": "…", "ad": "Örnek Müşteri", "telefon": "0532…", "notlar": "", "guncelleme": 1794600000000 } ],
    "islem":   [ { "uuid": "…", "musteri_uuid": "…", "tur": "SATIŞ", "tarih": "2026-11-13", "tutar": 35.0,
                   "aciklama": "", "fis_no": 190, "guncelleme": 1794600000000,
                   "kalemler": [ { "urun": "Örnek Ürün", "adet": 1, "birim_fiyat": 35.0 } ] } ],
    "gider":   [ { "uuid": "…", "tarih": "2026-11-13", "kategori": "Yakıt", "tutar": 750, "aciklama": "", "guncelleme": 1794600000000 } ],
    "silinen": [ { "uuid": "…", "tablo": "islem", "zaman": 1794600000000 } ]
  }
}
```

Cevap:
```json
{
  "api": 1,
  "rapor": { "yeni_musteri": 0, "birlesen_musteri": 0, "guncellenen_musteri": 0, "yeni_islem": 1,
             "guncellenen_islem": 0, "silinen": 1, "yeni_gider": 1,
             "fis_degisen": [ { "eski": 190, "yeni": 191, "uuid": "…" } ] },
  "son_surum": 1795,
  "daha_var": false,
  "musteri": [ … ], "islem": [ … ], "gider": [ … ],
  "bagli_musteri": [ … ],
  "esleme": [ { "eski": "…", "yeni": "…" } ]
}
```

- Cevaptaki kayıtlarda `silindi: 1` olanlar cihazda silinir.
- `daha_var: true` ise cihaz yeni `son_surum` ile tekrar sorar. Bir cevapta en fazla 1000 kayıt döner.
- Bir istekte en fazla 2000 kayıt gönderilebilir; istemciler 400'erli parçalar halinde gönderir.
- Cihaz sunucudaki sürümden ilerideyse (sunucu verisi silinmişse) cevap `{"sunucu_sifirlandi": true}` olur ve cihaz bütün kayıtlarını yeniden yükler.

### `GET /v1/disa-aktar`
Silinmemiş bütün kayıtların JSON yedeği.
```bash
curl -H "Authorization: Bearer <anahtar>" https://<adres>/v1/disa-aktar > yedek.json
```

### Hata kodları

| Kod | Anlamı | Cihazda görünen mesaj |
|---|---|---|
| 400 | Geçersiz veri | Sunucunun açıklaması |
| 401 | Anahtar yanlış | "Sunucu anahtarı hatalı." |
| 409 | Aynı anda iki cihaz eşitledi | "Tekrar deneyin" (sonraki otomatik denemede düzelir) |
| — | Bağlantı yok | "Sunucuya ulaşılamadı. İnternet bağlantınızı kontrol edin." / "Çevrimdışı · N bekleyen" |

## 5. Eşitleme kuralları

| Durum | Sonuç |
|---|---|
| Aynı kayıt iki cihazda da değiştirildi | **Son değişiklik kazanır** |
| Bir cihazda silindi | Diğer cihazdan da silinir, eski kopyadan geri gelmez |
| Silindikten sonra başka cihazda değiştirildi | Kayıt geri gelir |
| İki cihazda aynı isimle müşteri açıldı | **Tek müşteride birleşir**; boş telefon/not dolu olanla tamamlanır |
| İki cihaz çevrimdışıyken aynı fiş numarasını kullandı | **Önce eşitleyen numarasını korur**, diğerine sıradaki boş numara verilir ve kullanıcıya gösterilir |
| Silinen müşteriye başka cihazda sonradan satış girildi | Satış kaybolmasın diye **müşteri geri gelir** |
| İşlemi olan müşteriyi başka cihaz sildi | Gönderilmemiş işlem varsa müşteri silinmez |

"Son değişiklik", değişikliği yapan cihazın saatine göre belirlenir. Bu yüzden telefon ve laptopun saati otomatik (internetten) ayarlı olmalıdır.

## 6. Kurulum (sunucuyu yayınlama)

Gereken: ücretsiz bir Cloudflare hesabı ve Node.js.

```bash
cd sunucu
npm install
npx wrangler login                                  # tarayıcıda Cloudflare'e izin verin
npx wrangler d1 create ogul-tarim-muhasebe          # çıkan database_id'yi wrangler.toml'a yazın
npx wrangler d1 execute ogul-tarim-muhasebe --remote --file schema.sql
npx wrangler secret put API_ANAHTARI                # uzun, rastgele bir anahtar girin
npx wrangler deploy                                 # adresi verir: https://ogul-tarim-muhasebe.<hesap>.workers.dev
```

Sonra programda **Sunucu** düğmesine, uygulamada ana ekrandaki **Sunucu** düğmesine basıp adresi ve anahtarı girin.

Kendi bilgisayarınızda deneme:
```bash
npx wrangler d1 execute ogul-tarim-muhasebe --local --file schema.sql
npx wrangler dev --var API_ANAHTARI:deneme         # http://127.0.0.1:8787
```

## 7. Kapasite ve maliyet

Cloudflare'in ücretsiz plan sınırları (güncel değerleri Cloudflare sayfasından kontrol edin):
- Workers: günde 100.000 istek
- D1: 5 GB depolama, günde 5 milyon satır okuma, günde 100.000 satır yazma

Bu işletmenin kullanımı:
- İki cihaz açıkken dakikada birer eşitleme, yani 8 saatlik bir günde yaklaşık 1.000 istek.
- 1.000 müşteri ve 20.000 fiş birkaç MB tutar.

Sunucu, ücretsiz planın "istek başına en fazla 50 sorgu" sınırına göre tasarlandı: bir eşitleme isteği yaklaşık 15 sorgu yapar, kayıtlar JSON olarak toplu yazılır.

## 8. Yedekleme

- **Sunucu:** `GET /v1/disa-aktar` ile tam JSON yedeği alınabilir. Ayrıca her cihazda verinin tam bir kopyası durur.
- **Laptop:** Veritabanı yapısı değişmeden önce `Yedekler` klasörüne otomatik yedek alınır; son 30 yedek saklanır.
- **Excel:** Programdaki **Excel'e Aktar** düğmesi bütün müşterileri, fişleri, tahsilatları ve giderleri tek dosyaya yazar.

## 9. Test raporu

Testler yerel Cloudflare ortamında (`wrangler dev`, gerçek Workers çalışma zamanı ve yerel D1) yapıldı.

**Laptop istemcisi (Python), 29 senaryo, hepsi geçti:**
- Eski şemalı gerçek veritabanının kopyası yeni yapıya geçti; geçişten önce yedek alındı.
- 68 müşteri, 220 işlem ve 1.500 gider parça parça yüklendi; sunucudaki sayılar yereldekiyle aynı.
- Sıfırdan bir cihaz her şeyi sayfalı indirdi: bakiye toplamı, fiş numaraları ve ürün satırları birebir aynı.
- İki cihaz çevrimdışıyken aynı fiş numarasını kullandı: ilk eşitleyen korundu, ikinciye yeni numara verildi.
- Aynı isimle iki cihazda açılan müşteri tek müşteride birleşti; telefon ve not tamamlandı.
- Silme, düzenleme ve "son değişiklik kazanır" iki yöne de yayıldı.
- Silinen müşteriye başka cihazda girilen satış kaybolmadı.
- Sunucu sıfırlanınca cihaz bütün kayıtlarını yeniden yükledi.
- Yanlış anahtar ve internet yok durumunda doğru mesajlar çıktı.

**Telefon istemcisi (Dart/Flutter), 6 test, hepsi geçti:**
- Eski sürüm telefon veritabanı yükseltildi ve kayıtları gönderilecek olarak işaretlendi.
- Telefon sunucudan her şeyi aldı. Yeni müşteri, indirimli satış, tahsilat, silme ve gider gönderdi; ikinci eşitlemede hiçbir şey değişmedi.
- Telefondaki veri, sıfırdan eşitlenen bir laptopun verisiyle karşılaştırıldı: 225 işlem, 596 ürün satırı, müşteriler ve giderler birebir aynı.

**Programın arayüzü:** Başlıktaki "☁ Eşitlendi" durumu, Sunucu Ayarları'ndaki bağlantı testi ve yeni girilen tahsilatın 3 saniye içinde kendiliğinden gönderilmesi denendi.

**Henüz denenmeyenler:**
- Uygulamanın gerçek bir Android telefonda çalışması. Geliştirme bilgisayarında disk dolu olduğu için emülatör açılamadı.
- Gerçek Cloudflare hesabında, ücretsiz plan sınırları altında yük testi.
