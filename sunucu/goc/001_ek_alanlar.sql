-- 001: Genel "ek" alanları.
-- Uygulamaya ileride eklenen basit alanlar (adres, vergi no, birim ...) sunucu kodu ve yeni göç
-- gerektirmeden saklanır: sunucu tanımadığı alanları atmak yerine bu JSON sütununda tutar ve
-- cihazlara kaydın içinde düz alan olarak geri verir. Eski sürüm uygulama bir alanı göndermezse
-- mevcut değer korunur (json_patch ile birleştirilir); alanı silmek için null gönderilir.
-- Bu dosya uygulandıktan sonra değiştirilmez; düzeltme gerekirse yeni numaralı göç yazılır.

ALTER TABLE musteri ADD COLUMN ek TEXT NOT NULL DEFAULT '{}';
ALTER TABLE islem ADD COLUMN ek TEXT NOT NULL DEFAULT '{}';
ALTER TABLE gider ADD COLUMN ek TEXT NOT NULL DEFAULT '{}';

-- yalnızca "ek" değiştiğinde de kayıt diğer cihazlara gitsin
DROP TRIGGER IF EXISTS musteri_surum_guncelle;
CREATE TRIGGER musteri_surum_guncelle AFTER UPDATE OF ad, telefon, notlar, ek, guncelleme, silindi ON musteri BEGIN
    UPDATE meta SET deger = deger + 1 WHERE anahtar = 'surum';
    UPDATE musteri SET surum = (SELECT deger FROM meta WHERE anahtar = 'surum') WHERE uuid = NEW.uuid;
END;
DROP TRIGGER IF EXISTS islem_surum_guncelle;
CREATE TRIGGER islem_surum_guncelle AFTER UPDATE OF musteri_uuid, tur, tarih, tutar, aciklama, fis_no, kalemler, ek, guncelleme, silindi ON islem BEGIN
    UPDATE meta SET deger = deger + 1 WHERE anahtar = 'surum';
    UPDATE islem SET surum = (SELECT deger FROM meta WHERE anahtar = 'surum') WHERE uuid = NEW.uuid;
END;
DROP TRIGGER IF EXISTS gider_surum_guncelle;
CREATE TRIGGER gider_surum_guncelle AFTER UPDATE OF tarih, kategori, tutar, aciklama, ek, guncelleme, silindi ON gider BEGIN
    UPDATE meta SET deger = deger + 1 WHERE anahtar = 'surum';
    UPDATE gider SET surum = (SELECT deger FROM meta WHERE anahtar = 'surum') WHERE uuid = NEW.uuid;
END;

-- Uygulanan son göç (Cloudflare Workers kurulumu bunu okur; Node sunucusu ayrıca PRAGMA user_version tutar)
INSERT OR REPLACE INTO meta (anahtar, deger) VALUES ('goc', 1);
