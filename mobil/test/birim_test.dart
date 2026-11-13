import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ogul_tarim/durum.dart';
import 'package:ogul_tarim/ekstre/ekstre_pdf.dart';
import 'package:ogul_tarim/veri/veritabani.dart';
import 'package:ogul_tarim/yardimci.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

String yazim(String tuslar) {
  final b = TarihBicimi();
  var d = TextEditingValue.empty;
  for (final t in tuslar.split('')) {
    if (t == '<') {
      final y = d.text.substring(0, d.text.length - 1);
      d = b.formatEditUpdate(d, TextEditingValue(text: y, selection: TextSelection.collapsed(offset: y.length)));
    } else {
      d = b.formatEditUpdate(d, TextEditingValue(text: d.text + t, selection: TextSelection.collapsed(offset: d.text.length + 1)));
    }
  }
  return d.text;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('tarih bicimi', () {
    expect(yazim('06112026'), '06.11.2026');
    expect(yazim('06'), '06.');
    expect(yazim('0611'), '06.11.');
    expect(yazim('6.1.2026'), '06.01.2026');
    expect(yazim('06.11.2026'), '06.11.2026');
    expect(yazim('061120269999'), '06.11.2026');
    expect(yazim('0611<'), '06.11');
    expect(yazim('0611<<'), '06.1');
  });

  test('bicimler', () {
    expect(para(1234.5), '1.234,50 ₺');
    expect(para(1000000), '1.000.000,00 ₺');
    expect(para(-5), '-5,00 ₺');
    expect(para(0), '0,00 ₺');
    expect(adetYaz(3.0), '3');
    expect(adetYaz(2.5), '2,5');
    expect(adetYaz(10.0), '10');
    expect(adetYaz(100.0), '100');
    expect(sayiOku('1.234,50'), 1234.5);
    expect(sayiOku('1234.50'), 1234.5);
    expect(sayiOku('abc'), isNull);
    expect(tarihOku('06.11.2026'), '2026-11-06');
    expect(tarihOku('06.11.26'), '2026-11-06');
    expect(tarihOku('31.02.2026'), isNull);
    expect(kucuk('ALİ IŞIK'), 'ali ışık');
  });

  test('veritabani hesaplari ve ekstre', () async {
    sqfliteFfiInit();
    vt = await Veritabani.ac(fabrika: databaseFactoryFfi, yol: inMemoryDatabasePath);
    final a = await vt.musteriKaydet(ad: 'Mehmet Öztürk', telefon: '0532');
    await vt.satisKaydet(musteriUuid: a, tarih: '2025-09-10', kalemler: const [Kalem('Buğday Tohumu', 4, 850)], fisNo: 1);
    await vt.tahsilatKaydet(musteriUuid: a, tarih: '2025-12-01', tutar: 1000);
    await vt.satisKaydet(musteriUuid: a, tarih: '2026-03-15', kalemler: const [Kalem('İlaç', 3, 420), Kalem('İNDİRİM', 1, -100)], fisNo: 2, aciklama: 'tarla');
    final b = await vt.musteriKaydet(ad: 'İsmail Temiz');
    await vt.satisKaydet(musteriUuid: b, tarih: '2025-05-01', kalemler: const [Kalem('Çapa', 1, 100)], fisNo: 3);
    await vt.tahsilatKaydet(musteriUuid: b, tarih: '2025-06-01', tutar: 100);

    expect(await vt.devir(a, 2026), 2400);
    expect((await vt.musteriler(yil: 2026)).map((m) => m.ad), ['Mehmet Öztürk'], reason: 'borcu kapanmis eski musteri yeni yilda listelenmez');
    expect((await vt.musteriler(ara: 'ismail', yil: 2026)).length, 1, reason: 'aramada hepsi bulunur');
    expect((await vt.musteriler(yil: 2026)).first.bakiye, 3560);
    expect(await vt.sonrakiFisNo(), 4);
    expect(await vt.fisKullanan(2, null), contains('Mehmet'));
    expect(await vt.sonFiyat('İlaç'), 420);
    expect(await vt.musteriBul('MEHMET ÖZTÜRK'), a);
    expect((await vt.sonIslemler(adet: 1)).first.musteriAd, 'İsmail Temiz');
    expect(await vt.yillar(), [DateTime.now().year, for (var y = DateTime.now().year - 1; y >= 2025; y--) y]);
    final o = await vt.ozet('2026-01-01', '2026-12-31');
    expect(o['ciro'], 1160);
    expect(o['alacak'], 3560);

    await vt.musteriSil(b);
    final (v, isaret) = await vt.kirlileriTopla(400);
    expect(v['musteri']!.length, 1, reason: 'once musteriler gonderilir');
    expect(await vt.bekleyenSayisi(), 1 + 3 + 3, reason: 'kalan musteri, 3 islem, musteri+iki islemin silme izi');
    expect(isaret.length, 1);

    final veri = await ekstreVerisi(a, 2026);
    expect(veri.devir, 2400);
    expect(veri.bakiye, 3560);
    final pdf = await ekstrePdf(veri);
    expect(String.fromCharCodes(pdf.sublist(0, 4)), '%PDF');
    final kalabalik = EkstreVeri('Uzun', '', null, 0, 0, 0, 0, [
      for (var i = 0; i < 400; i++) (const Islem('u', 'm', 'x', satisTur, '2026-01-01', 5, '', 7, [Kalem('Ürün', 1, 5)]), 5.0)
    ]);
    final buyuk = await ekstrePdf(kalabalik);
    expect(buyuk.length, greaterThan(pdf.length));
    File('${Platform.environment['CIKTI'] ?? Directory.systemTemp.path}/ekstre_test.pdf').writeAsBytesSync(pdf);
    await vt.db.close();
  });
}
