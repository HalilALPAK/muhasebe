// Gerçek telefonda, gerçek ekranlarla uçtan uca test. Laptop tarafı aynı anda bilgisayarda çalışır;
// telefon USB üzerinden (adb reverse tcp:8787) bilgisayardaki yerel test sunucusuna bağlanır.
//   flutter test integration_test/cihaz_test.dart -d <cihaz>
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:integration_test/integration_test.dart';
import 'package:path_provider/path_provider.dart';
import 'package:ogul_tarim/durum.dart';
import 'package:ogul_tarim/ekranlar/ortak.dart';
import 'package:ogul_tarim/main.dart';
import 'package:ogul_tarim/veri/bulut.dart';
import 'package:ogul_tarim/veri/veritabani.dart';

const url = 'http://127.0.0.1:8787', anahtar = 'testanahtari123';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('telefon: eşitleme, öneri, hesap, satış, tahsilat, ekstre', (t) async {
    final adimlar = <String>[];
    void not(String s) {
      adimlar.add(s);
      // ignore: avoid_print
      print('ADIM: $s');
    }

    Future<void> bekle(Finder f, {int saniye = 30, String? neden}) async {
      final son = DateTime.now().add(Duration(seconds: saniye));
      while (DateTime.now().isBefore(son)) {
        await t.pump(const Duration(milliseconds: 200));
        if (f.evaluate().isNotEmpty) return;
      }
      fail('Bulunamadı (${neden ?? f}): ${adimlar.join(' > ')}');
    }

    Future<void> dokun(Finder f) async {
      await t.ensureVisible(f.first);
      await t.pump(const Duration(milliseconds: 300));
      await t.tap(f.first);
      await t.pump(const Duration(milliseconds: 500));
    }

    Future<void> yaz(Finder f, String metin) async {
      await t.ensureVisible(f);
      await t.enterText(f, metin);
      await t.pump(const Duration(milliseconds: 400));
    }

    vt = await Veritabani.ac();
    esitleyici = BulutEsitleyici(vt);
    await t.pumpWidget(const OgulTarimUygulamasi());
    await bekle(find.text('OĞUL TARIM'));
    not('uygulama acildi');

    // --- sunucu ayarları ekrandan girilir ve bağlantı test edilir
    await dokun(find.text('Sunucu'));
    await bekle(find.text('Sunucu Ayarları'));
    final alanlar = find.byType(TextField);
    await yaz(alanlar.at(0), url);
    await yaz(alanlar.at(1), anahtar);
    await yaz(alanlar.at(2), 'telefon-test');
    await dokun(find.text('Bağlantıyı Test Et'));
    await bekle(find.textContaining('Bağlantı başarılı'), neden: 'sunucu bağlantısı');
    not('sunucu baglantisi basarili');
    await dokun(find.text('Kaydet ve Eşitle'));
    for (var i = 0; i < 100 && await vt.musteriBul('deneme çiftçi') == null; i++) {
      await t.pump(const Duration(milliseconds: 300));
    }
    expect(await vt.musteriBul('deneme çiftçi'), isNotNull, reason: 'laptopta açılan müşteri telefona gelmeli');
    not('laptoptaki musteri telefona geldi');

    // --- FİŞ: harf yazınca öneri, seçince hesap
    await dokun(find.byKey(const Key('dugme_FİŞ')));
    await bekle(find.text('Son Girilen İşlemler'));
    await yaz(find.byType(TextField).first, 'den');
    await bekle(find.widgetWithText(ListTile, 'Deneme Çiftçi'), neden: 'öneri');
    not('oneri geldi');
    await dokun(find.widgetWithText(ListTile, 'Deneme Çiftçi'));
    await bekle(find.text('Tel: 0555 111 22 33'));
    expect(find.text('200,00 ₺'), findsWidgets);
    not('hesap gorundu: 200 TL');

    // --- tahsilat (ekrandan)
    await dokun(find.text('+ Tahsilat'));
    await bekle(find.text('Tahsilat (Ödeme Al)'));
    await yaz(find.byType(TextField).at(1), '80');
    await yaz(find.byType(TextField).at(2), 'nakit');
    await dokun(find.text('KAYDET'));
    await bekle(find.text('Son Girilen İşlemler'));
    not('tahsilat girildi');

    // --- aynı müşteriye satış (ekrandan; ürün, adet, fiyat)
    await dokun(find.text('+ Satış Yap'));
    await bekle(find.text('Yeni Satış'));
    var a = find.byType(TextField);
    await yaz(a.at(3), 'Tohum');
    await yaz(a.at(4), '3');
    await yaz(a.at(5), '10');
    await dokun(find.text('Ekle'));
    await bekle(find.text('30,00 ₺'));
    await dokun(find.byKey(const Key('satis_kaydet')));
    await bekle(find.text('Son Girilen İşlemler'));
    not('satis girildi');

    // --- kayıtlı olmayan müşteriye satış: müşteri kendiliğinden açılır
    await dokun(find.byKey(const Key('yeni_satis')));
    await bekle(find.text('Yeni Satış'));
    a = find.byType(TextField);
    await yaz(a.at(0), 'Telefondan Yeni');
    await yaz(a.at(3), 'Çapa');
    await yaz(a.at(4), '1');
    await yaz(a.at(5), '75');
    await dokun(find.text('Ekle'));
    await bekle(find.text('75,00 ₺'));
    await dokun(find.byKey(const Key('satis_kaydet')));
    await bekle(find.text('Son Girilen İşlemler'));
    expect(await vt.musteriBul('telefondan yeni'), isNotNull);
    not('yeni musteri satisla acildi');

    // --- gönder; laptop aynı müşteriye satış girene kadar bekle (bilgisayardaki betik yapar)
    final deneme = (await vt.musteriBul('deneme çiftçi'))!;
    var tamam = false;
    for (var i = 0; i < 60 && !tamam; i++) {
      await esitleyici.simdi();
      tamam = (await vt.islemler(deneme)).length == 4;
      if (!tamam) await Future<void>.delayed(const Duration(seconds: 2));
    }
    expect(tamam, isTrue, reason: 'laptopun girdiği satış telefona gelmeli');
    not('laptopun satisi telefona geldi');
    expect(await vt.bekleyenSayisi(), 0);

    // --- CARİ: dört işlem ve bakiye
    t.state<NavigatorState>(find.byType(Navigator).first).popUntil((r) => r.isFirst); // ana ekrana dön
    await bekle(find.byKey(const Key('dugme_CARİ')));
    await dokun(find.byKey(const Key('dugme_CARİ')));
    await bekle(find.text('Telefondan Yeni'));
    await dokun(find.text('Deneme Çiftçi'));
    await bekle(find.byType(IslemKarti));
    await t.pump(const Duration(seconds: 1));
    expect(find.byType(IslemKarti), findsNWidgets(4));
    final kalan = find.ancestor(of: find.text('Kalan Borç'), matching: find.byType(Column)).first;
    expect(find.descendant(of: kalan, matching: find.text('200,00 ₺')), findsOneWidget, reason: '200 - 80 + 30 + 50');
    not('cari: 4 islem, kalan 200 TL');

    // --- ekstre: PDF ve görsel telefonda üretilir
    await dokun(find.text('WhatsApp / Ekstre Gönder'));
    // paylaş düğmesi ancak PDF ve görsel hazır olunca etkinleşir
    final paylas = find.ancestor(of: find.text('Görsel + PDF Paylaş (WhatsApp)'), matching: find.byWidgetPredicate((w) => w is ButtonStyleButton));
    bool hazir() => t.widget<ButtonStyleButton>(paylas.first).onPressed != null;
    final son = DateTime.now().add(const Duration(seconds: 90));
    while (DateTime.now().isBefore(son) && !hazir()) {
      await t.pump(const Duration(milliseconds: 300));
    }
    expect(hazir(), isTrue, reason: 'ekstre 90 saniyede hazırlanmalı');
    expect(find.descendant(of: find.byType(InteractiveViewer), matching: find.byType(Image)), findsWidgets, reason: 'görsel önizleme');
    final dosyalar = (await getTemporaryDirectory()).listSync().whereType<File>().where((f) => f.path.contains('Ekstre_Deneme')).toList();
    // ignore: avoid_print
    print('EKSTRE DOSYALARI: ${dosyalar.map((f) => '${f.path.split('/').last} ${f.lengthSync()}').join(', ')}');
    expect(dosyalar.any((f) => f.path.endsWith('.pdf') && f.lengthSync() > 1000), isTrue, reason: 'PDF üretilmeli');
    expect(dosyalar.any((f) => f.path.endsWith('.png') && f.lengthSync() > 1000), isTrue, reason: 'PNG üretilmeli');
    not('ekstre pdf+png uretildi');
    // görselin pikselleri: arka plan opak beyaz, yazılar koyu olmalı (WhatsApp'a bu gider)
    final png = img.decodePng(dosyalar.firstWhere((f) => f.path.endsWith('.png')).readAsBytesSync())!;
    final kose = png.getPixel(5, 5);
    var koyu = 0;
    for (var y = 0; y < png.height; y += 4) {
      for (var x = 0; x < png.width; x += 4) {
        final p = png.getPixel(x, y);
        if (p.r < 90 && p.g < 90 && p.b < 90) koyu++;
      }
    }
    final oran = koyu / ((png.width / 4) * (png.height / 4));
    // ignore: avoid_print
    print('PNG: ${png.width}x${png.height} kanal=${png.numChannels} kose=(${kose.r},${kose.g},${kose.b},${kose.a}) koyu_oran=${(oran * 100).toStringAsFixed(2)}%');
    expect((kose.r, kose.g, kose.b), (255, 255, 255), reason: 'arka plan beyaz olmalı');
    if (png.numChannels == 4) expect(kose.a, 255, reason: 'arka plan opak olmalı');
    expect(oran, greaterThan(0.002), reason: 'koyu yazılar olmalı');
    not('ekstre gorseli dogru: beyaz zemin, koyu yazi');
    // ignore: avoid_print
    print('PNG_HAZIR');
    await t.pump(const Duration(seconds: 12)); // bilgisayar bu sırada görseli telefondan çeker
    // önizleme görseli gerçekten ekrana çizildi mi (çözülmüş görüntü ve gerçek boyut)
    final cizildi = DateTime.now().add(const Duration(seconds: 20));
    RenderImage? goruntu;
    while (DateTime.now().isBefore(cizildi)) {
      await t.pump(const Duration(milliseconds: 300));
      final r = find.descendant(of: find.byType(InteractiveViewer), matching: find.byType(RawImage));
      if (r.evaluate().isNotEmpty) {
        goruntu = t.renderObject<RenderImage>(r.first);
        if (goruntu.image != null && goruntu.size.height > 100) break;
      }
    }
    // ignore: avoid_print
    print('ONIZLEME: goruntu=${goruntu?.image != null} boyut=${goruntu?.size}');
    expect(goruntu?.image, isNotNull, reason: 'önizleme görseli ekrana çizilmeli');
    expect(goruntu!.size.height, greaterThan(100));
    not('onizleme ekranda gorundu');
    // ignore: avoid_print
    print('FOTO_CEK');
    await t.pump(const Duration(seconds: 6)); // bilgisayar bu sırada ekran görüntüsü alır
    // ignore: avoid_print
    print('TELEFON TAMAM: ${adimlar.join(' > ')}');
  }, timeout: const Timeout(Duration(minutes: 8)));
}
