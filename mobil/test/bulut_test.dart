// Yerel/uzak sunucuyla uçtan uca test. BULUT_URL, BULUT_ANAHTAR ve TEL_DB ortam değişkenleri gerekir.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:ogul_tarim/veri/bulut.dart';
import 'package:ogul_tarim/veri/veritabani.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  final url = Platform.environment['BULUT_URL'];
  final anahtar = Platform.environment['BULUT_ANAHTAR'] ?? '';
  sqfliteFfiInit();

  test('eski surum veritabani yukseltilir, kayitlar gonderilecek olur', () async {
    final yol = '${Directory.systemTemp.createTempSync('v1').path}/v1.db';
    final eski = await databaseFactoryFfi.openDatabase(yol, options: OpenDatabaseOptions(version: 1, onCreate: (d, _) async {
      await d.execute("CREATE TABLE musteri (uuid TEXT PRIMARY KEY, ad TEXT NOT NULL, telefon TEXT DEFAULT '', notlar TEXT DEFAULT '', guncelleme INTEGER NOT NULL)");
      await d.execute("CREATE TABLE islem (uuid TEXT PRIMARY KEY, musteri_uuid TEXT NOT NULL, tur TEXT NOT NULL, tarih TEXT NOT NULL, tutar REAL NOT NULL, aciklama TEXT DEFAULT '', fis_no INTEGER, guncelleme INTEGER NOT NULL)");
      await d.execute('CREATE TABLE kalem (id INTEGER PRIMARY KEY AUTOINCREMENT, islem_uuid TEXT NOT NULL, urun TEXT NOT NULL, adet REAL NOT NULL, birim_fiyat REAL NOT NULL)');
      await d.execute("CREATE TABLE gider (uuid TEXT PRIMARY KEY, tarih TEXT NOT NULL, kategori TEXT DEFAULT '', tutar REAL NOT NULL, aciklama TEXT DEFAULT '', guncelleme INTEGER NOT NULL)");
      await d.execute('CREATE TABLE silinen (uuid TEXT PRIMARY KEY, tablo TEXT NOT NULL, zaman INTEGER NOT NULL)');
      await d.execute('CREATE TABLE ayar (anahtar TEXT PRIMARY KEY, deger TEXT)');
      await d.insert('musteri', {'uuid': 'eskimusteri0001', 'ad': 'Eski Kayıt', 'guncelleme': 1});
    }));
    await eski.close();
    final vt = await Veritabani.ac(fabrika: databaseFactoryFfi, yol: yol);
    expect(await vt.bekleyenSayisi(), 1);
    expect((await vt.musteriler()).single.ad, 'Eski Kayıt');
    await vt.db.close();
  });

  test('sunucu yoksa ve anahtar yanlissa dogru mesaj', () async {
    final vt = await Veritabani.ac(fabrika: databaseFactoryFfi, yol: inMemoryDatabasePath);
    await expectLater(esitle(vt, 'http://127.0.0.1:9', 'x', 't'), throwsA(isA<BulutHatasi>().having((e) => e.mesaj, 'm', internetMesaji)));
    if (url != null) {
      await expectLater(esitle(vt, url, 'yanlis', 't'), throwsA(isA<BulutHatasi>().having((e) => e.mesaj, 'm', contains('anahtarı hatalı'))));
    }
    await vt.db.close();
  });

  test('telefon sunucudan alir, degisiklikleri gonderir', () async {
    final yol = Platform.environment['TEL_DB']!;
    final vt = await Veritabani.ac(fabrika: databaseFactoryFfi, yol: yol);
    final d = await durumSor(url!, anahtar);

    var s = await esitle(vt, url, anahtar, 'telefon-test');
    expect(s.alinan, greaterThan(0));
    expect(await vt.bekleyenSayisi(), 0);
    expect((await vt.sonIslemler(adet: 100000)).length, d['islem']);
    expect((await vt.giderler('0000-01-01', '9999-12-31')).length, d['gider']);

    final fis = await vt.sonrakiFisNo();
    final m = await vt.musteriKaydet(ad: 'Telefondan Gelen', telefon: '0533');
    await vt.satisKaydet(musteriUuid: m, tarih: '2026-11-13', kalemler: const [Kalem('TEL ÜRÜN', 3, 12.5), Kalem('İNDİRİM', 1, -2.5)], fisNo: fis);
    final ilkMusteri = (await vt.musteriler()).first.uuid;
    await vt.tahsilatKaydet(musteriUuid: ilkMusteri, tarih: '2026-11-13', tutar: 1234.5, aciklama: 'tel');
    final ilk = (await vt.sonIslemler(adet: 100000)).last;
    await vt.islemSil(ilk.uuid);
    await vt.giderEkle('2026-11-13', 'Telefon', 42, '');
    expect(await vt.bekleyenSayisi(), 5, reason: "musteri, satis, tahsilat, silme izi, gider");

    s = await esitle(vt, url, anahtar, 'telefon-test');
    expect(s.gonderilen, 5);
    expect(await vt.bekleyenSayisi(), 0);
    s = await esitle(vt, url, anahtar, 'telefon-test');
    expect((s.gonderilen, s.alinan), (0, 0), reason: 'tekrar esitleme bir sey degistirmez');
    await vt.db.close();
  }, skip: url == null, timeout: const Timeout(Duration(minutes: 3)));
}
