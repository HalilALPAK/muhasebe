-- Oğul Tarım Muhasebe - Cloudflare D1 şeması
-- Her kayıt uuid ile tanınır. Silinen kayıtlar silindi=1 olarak kalır (eşitlemede geri gelmesin diye).
-- surum: her yazmada artan genel sayaç; cihazlar "şu sürümden sonrasını ver" diye sorar.

CREATE TABLE IF NOT EXISTS meta (
    anahtar TEXT PRIMARY KEY,
    deger INTEGER NOT NULL
);
INSERT OR IGNORE INTO meta (anahtar, deger) VALUES ('surum', 0);

CREATE TABLE IF NOT EXISTS musteri (
    uuid TEXT PRIMARY KEY,
    ad TEXT NOT NULL DEFAULT '',
    telefon TEXT NOT NULL DEFAULT '',
    notlar TEXT NOT NULL DEFAULT '',
    guncelleme INTEGER NOT NULL,          -- son değişikliğin zamanı (ms, değişikliği yapan cihazın saati)
    silindi INTEGER NOT NULL DEFAULT 0,
    surum INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS islem (
    uuid TEXT PRIMARY KEY,
    musteri_uuid TEXT NOT NULL DEFAULT '',
    tur TEXT NOT NULL DEFAULT 'SATIŞ',    -- 'SATIŞ' veya 'TAHSİLAT'
    tarih TEXT NOT NULL DEFAULT '',       -- YYYY-AA-GG
    tutar REAL NOT NULL DEFAULT 0,
    aciklama TEXT NOT NULL DEFAULT '',
    fis_no INTEGER,                       -- sadece satışlarda
    kalemler TEXT NOT NULL DEFAULT '[]',  -- [{"urun","adet","birim_fiyat"}]
    guncelleme INTEGER NOT NULL,
    silindi INTEGER NOT NULL DEFAULT 0,
    surum INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS gider (
    uuid TEXT PRIMARY KEY,
    tarih TEXT NOT NULL DEFAULT '',
    kategori TEXT NOT NULL DEFAULT '',
    tutar REAL NOT NULL DEFAULT 0,
    aciklama TEXT NOT NULL DEFAULT '',
    guncelleme INTEGER NOT NULL,
    silindi INTEGER NOT NULL DEFAULT 0,
    surum INTEGER NOT NULL DEFAULT 0
);

-- İki cihazda aynı isimle açılan müşteriler birleştirilir: eski uuid -> kalan uuid
CREATE TABLE IF NOT EXISTS esleme (
    eski TEXT PRIMARY KEY,
    yeni TEXT NOT NULL
);

-- Eşitleme kayıtları (hangi cihaz ne zaman ne gönderdi)
CREATE TABLE IF NOT EXISTS kayit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman INTEGER NOT NULL,
    cihaz TEXT NOT NULL DEFAULT '',
    gelen INTEGER NOT NULL DEFAULT 0,
    giden INTEGER NOT NULL DEFAULT 0,
    rapor TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS musteri_surum ON musteri(surum);
CREATE INDEX IF NOT EXISTS islem_surum ON islem(surum);
CREATE INDEX IF NOT EXISTS gider_surum ON gider(surum);
CREATE INDEX IF NOT EXISTS islem_musteri ON islem(musteri_uuid);
CREATE UNIQUE INDEX IF NOT EXISTS islem_fis_no ON islem(fis_no) WHERE silindi = 0 AND fis_no IS NOT NULL;

-- Her ekleme/güncellemede kayda yeni sürüm numarası verilir (aynı işlem içinde, yarışsız)
CREATE TRIGGER IF NOT EXISTS musteri_surum_ekle AFTER INSERT ON musteri BEGIN
    UPDATE meta SET deger = deger + 1 WHERE anahtar = 'surum';
    UPDATE musteri SET surum = (SELECT deger FROM meta WHERE anahtar = 'surum') WHERE uuid = NEW.uuid;
END;
CREATE TRIGGER IF NOT EXISTS musteri_surum_guncelle AFTER UPDATE OF ad, telefon, notlar, guncelleme, silindi ON musteri BEGIN
    UPDATE meta SET deger = deger + 1 WHERE anahtar = 'surum';
    UPDATE musteri SET surum = (SELECT deger FROM meta WHERE anahtar = 'surum') WHERE uuid = NEW.uuid;
END;
CREATE TRIGGER IF NOT EXISTS islem_surum_ekle AFTER INSERT ON islem BEGIN
    UPDATE meta SET deger = deger + 1 WHERE anahtar = 'surum';
    UPDATE islem SET surum = (SELECT deger FROM meta WHERE anahtar = 'surum') WHERE uuid = NEW.uuid;
END;
CREATE TRIGGER IF NOT EXISTS islem_surum_guncelle AFTER UPDATE OF musteri_uuid, tur, tarih, tutar, aciklama, fis_no, kalemler, guncelleme, silindi ON islem BEGIN
    UPDATE meta SET deger = deger + 1 WHERE anahtar = 'surum';
    UPDATE islem SET surum = (SELECT deger FROM meta WHERE anahtar = 'surum') WHERE uuid = NEW.uuid;
END;
CREATE TRIGGER IF NOT EXISTS gider_surum_ekle AFTER INSERT ON gider BEGIN
    UPDATE meta SET deger = deger + 1 WHERE anahtar = 'surum';
    UPDATE gider SET surum = (SELECT deger FROM meta WHERE anahtar = 'surum') WHERE uuid = NEW.uuid;
END;
CREATE TRIGGER IF NOT EXISTS gider_surum_guncelle AFTER UPDATE OF tarih, kategori, tutar, aciklama, guncelleme, silindi ON gider BEGIN
    UPDATE meta SET deger = deger + 1 WHERE anahtar = 'surum';
    UPDATE gider SET surum = (SELECT deger FROM meta WHERE anahtar = 'surum') WHERE uuid = NEW.uuid;
END;
