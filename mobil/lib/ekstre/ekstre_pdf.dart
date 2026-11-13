import 'dart:typed_data';

import 'package:flutter/services.dart' show rootBundle;
import 'package:image/image.dart' as img;
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

import '../durum.dart';
import '../veri/veritabani.dart';
import '../yardimci.dart';

class EkstreVeri {
  final String ad, telefon;
  final int? yil;
  final double devir, satis, tahsilat, bakiye;
  final List<(Islem, double)> islemler;
  const EkstreVeri(this.ad, this.telefon, this.yil, this.devir, this.satis, this.tahsilat, this.bakiye, this.islemler);
}

/// Ekstre içeriği. [yil] verilirse önceki yıllar devir olarak tek satıra iner.
Future<EkstreVeri> ekstreVerisi(String musteriUuid, int? yil) async {
  final m = (await vt.musteri(musteriUuid))!;
  final devir = yil != null ? await vt.devir(musteriUuid, yil) : 0.0;
  var bakiye = devir;
  double s = 0, t = 0;
  final l = <(Islem, double)>[];
  for (final i in await vt.islemler(musteriUuid, yil: yil)) {
    if (i.satis) {
      s += i.tutar;
      bakiye += i.tutar;
    } else {
      t += i.tutar;
      bakiye -= i.tutar;
    }
    l.add((i, bakiye));
  }
  return EkstreVeri(m.ad, m.telefon, yil, devir, s, t, bakiye, l);
}

final _turuncu = PdfColor.fromInt(turuncu.toARGB32());
final _koyu = PdfColor.fromInt(koyuTuruncu.toARGB32());
final _acik = PdfColor.fromInt(acikTuruncu.toARGB32());
final _yesil = PdfColor.fromInt(yesil.toARGB32());
const _yazi = PdfColor.fromInt(0xFF2A1A0A);
const _gri = PdfColor.fromInt(0xFF666666);
const _cizgi = PdfColor.fromInt(0xFFEDE3D9);
const _bant = PdfColor.fromInt(0xFFFFF6EC);

const _kolonlar = [('Tarih', 12, false), ('İşlem / Ürün', 27, false), ('Adet', 6, true), ('Birim Fiyat', 12, true), ('Tutar', 13, true), ('Borç', 13, true), ('Ödeme', 12, true), ('Bakiye', 14, true)];

pw.Widget _satir(List<String> h, {PdfColor? zemin, PdfColor renk = _yazi, bool kalin = false, double boyut = 8.5, bool cizgi = true, PdfColor? bakiyeRenk}) => pw.Container(
      padding: const pw.EdgeInsets.symmetric(vertical: 3.5, horizontal: 4),
      decoration: pw.BoxDecoration(color: zemin, border: cizgi ? const pw.Border(bottom: pw.BorderSide(color: _cizgi, width: 0.5)) : null),
      child: pw.Row(children: [
        for (var i = 0; i < _kolonlar.length; i++)
          pw.Expanded(
            flex: _kolonlar[i].$2,
            child: pw.Text(h[i],
                textAlign: _kolonlar[i].$3 ? pw.TextAlign.right : pw.TextAlign.left,
                maxLines: 2,
                style: pw.TextStyle(fontSize: boyut, fontWeight: kalin ? pw.FontWeight.bold : pw.FontWeight.normal, color: i == 7 ? (bakiyeRenk ?? _yazi) : renk)),
          ),
      ]),
    );

pw.Widget _tabloBasligi() => _satir([for (final k in _kolonlar) k.$1], zemin: _turuncu, renk: PdfColors.white, kalin: true, boyut: 8.5, cizgi: false, bakiyeRenk: PdfColors.white);

List<pw.Widget> _satirlar(EkstreVeri v) {
  final s = <pw.Widget>[];
  final y = v.yil;
  if (y != null && v.devir.abs() > 0.005) {
    s.add(_satir(['01.01.$y', '${y - 1} yılından devir', '', '', '', v.devir > 0 ? para(v.devir) : '', v.devir < 0 ? para(-v.devir) : '', para(v.devir)], zemin: _acik, kalin: true));
  }
  for (final (i, b) in v.islemler) {
    if (i.satis) {
      s.add(_satir([tarihGoster(i.tarih), 'Fiş No: ${i.fisNo}${i.aciklama.isNotEmpty ? '  (${i.aciklama})' : ''}', '', '', '', para(i.tutar), '', para(b)], zemin: _bant, kalin: true));
      for (final k in i.kalemler) {
        s.add(_satir(['', '• ${k.urun}', adetYaz(k.adet), para(k.fiyat), para(k.tutar), '', '', ''], renk: _gri, boyut: 8));
      }
    } else {
      s.add(_satir([tarihGoster(i.tarih), 'Ödeme${i.aciklama.isNotEmpty ? '  (${i.aciklama})' : ''}', '', '', '', '', para(i.tutar), para(b)], renk: _yesil, kalin: true));
    }
  }
  if (s.isEmpty) s.add(_satir(['', 'Kayıtlı işlem bulunmuyor.', '', '', '', '', '', ''], renk: _gri));
  return s;
}

Future<Uint8List> ekstrePdf(EkstreVeri v) async {
  final logo = pw.MemoryImage((await rootBundle.load('assets/logo.jpg')).buffer.asUint8List());
  final tema = pw.ThemeData.withFont(
    base: pw.Font.ttf(await rootBundle.load('assets/fonts/roboto-regular.ttf')),
    bold: pw.Font.ttf(await rootBundle.load('assets/fonts/roboto-bold.ttf')),
  );
  final simdi = DateTime.now();
  final saat = '${simdi.hour.toString().padLeft(2, '0')}:${simdi.minute.toString().padLeft(2, '0')}';

  pw.Widget kutu(String e, double d, bool son) => pw.Expanded(
        child: pw.Container(
          margin: const pw.EdgeInsets.symmetric(horizontal: 3),
          padding: const pw.EdgeInsets.symmetric(vertical: 7),
          decoration: pw.BoxDecoration(
              color: son ? _turuncu : PdfColors.white,
              border: pw.Border.all(color: son ? _turuncu : const PdfColor.fromInt(0xFFE6D5C3)),
              borderRadius: pw.BorderRadius.circular(6)),
          child: pw.Column(children: [
            pw.Text(e, style: pw.TextStyle(fontSize: 9, color: son ? PdfColors.white : _gri, fontWeight: son ? pw.FontWeight.bold : pw.FontWeight.normal)),
            pw.SizedBox(height: 3),
            pw.Text(para(d), style: pw.TextStyle(fontSize: 13, fontWeight: pw.FontWeight.bold, color: son ? PdfColors.white : _yazi)),
          ]),
        ),
      );

  final y = v.yil;
  final gecmisYil = y != null && y < simdi.year;
  final borcEtiket = v.bakiye < -0.005 ? 'ALACAK BAKİYENİZ:' : (gecmisYil ? '$y YILI SONU BORÇ BAKİYENİZ:' : 'GÜNCEL BORÇ BAKİYENİZ:');

  final belge = pw.Document();
  belge.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    theme: tema,
    maxPages: 500,
    margin: const pw.EdgeInsets.fromLTRB(32, 26, 32, 26),
    header: (c) => c.pageNumber == 1
        ? pw.SizedBox()
        : pw.Column(crossAxisAlignment: pw.CrossAxisAlignment.stretch, children: [
            pw.Row(children: [
              pw.Image(logo, height: 40),
              pw.SizedBox(width: 10),
              pw.Column(crossAxisAlignment: pw.CrossAxisAlignment.start, children: [
                pw.Text(firma, style: pw.TextStyle(fontSize: 15, fontWeight: pw.FontWeight.bold, color: _turuncu)),
                pw.Text('Hesap Ekstresi – ${v.ad}', style: const pw.TextStyle(fontSize: 9, color: _gri)),
              ]),
            ]),
            pw.Container(height: 2.5, color: _turuncu, margin: const pw.EdgeInsets.symmetric(vertical: 6)),
            _tabloBasligi(),
          ]),
    footer: (c) => pw.Align(
          alignment: pw.Alignment.centerRight,
          child: pw.Text('Sayfa ${c.pageNumber}/${c.pagesCount}', style: const pw.TextStyle(fontSize: 8.5, color: _gri)),
        ),
    build: (c) => [
      pw.Row(children: [
        pw.Image(logo, height: 76),
        pw.SizedBox(width: 14),
        pw.Column(crossAxisAlignment: pw.CrossAxisAlignment.start, children: [
          pw.Text(firma, style: pw.TextStyle(fontSize: 26, fontWeight: pw.FontWeight.bold, color: _turuncu)),
          pw.Text('HESAP EKSTRESİ', style: pw.TextStyle(fontSize: 13, fontWeight: pw.FontWeight.bold, color: const PdfColor.fromInt(0xFF5A4A3A))),
        ]),
        pw.Spacer(),
        pw.Column(crossAxisAlignment: pw.CrossAxisAlignment.end, children: [
          pw.Text('Tarih: ${bugunGoster()}', style: const pw.TextStyle(fontSize: 10, color: _gri)),
        ]),
      ]),
      pw.Container(height: 3, color: _turuncu, margin: const pw.EdgeInsets.symmetric(vertical: 10)),
      pw.Container(
        padding: const pw.EdgeInsets.all(11),
        decoration: pw.BoxDecoration(color: _acik, borderRadius: pw.BorderRadius.circular(7)),
        child: pw.Row(crossAxisAlignment: pw.CrossAxisAlignment.end, children: [
          pw.Expanded(
            child: pw.Column(crossAxisAlignment: pw.CrossAxisAlignment.start, children: [
              pw.Text('SAYIN', style: pw.TextStyle(fontSize: 8.5, fontWeight: pw.FontWeight.bold, color: _koyu)),
              pw.SizedBox(height: 3),
              pw.Text(v.ad, style: pw.TextStyle(fontSize: 15, fontWeight: pw.FontWeight.bold, color: _yazi)),
            ]),
          ),
          pw.Column(crossAxisAlignment: pw.CrossAxisAlignment.end, children: [
            if (v.telefon.isNotEmpty) pw.Text('Tel: ${v.telefon}', style: const pw.TextStyle(fontSize: 9.5, color: _gri)),
            pw.SizedBox(height: 3),
            pw.Text(y != null ? 'Dönem: $y yılı (önceki yıllar devir)' : 'Dönem: Tüm işlemler', style: const pw.TextStyle(fontSize: 9.5, color: _gri)),
          ]),
        ]),
      ),
      pw.SizedBox(height: 10),
      pw.Row(children: [
        if (y != null) kutu('Önceki Yıldan Devir', v.devir, false),
        kutu('Toplam Alışveriş', v.satis, false),
        kutu('Toplam Ödeme', v.tahsilat, false),
        kutu(v.bakiye < -0.005 ? 'Alacağınız' : 'KALAN BORÇ', v.bakiye.abs(), true),
      ]),
      pw.SizedBox(height: 12),
      _tabloBasligi(),
      ..._satirlar(v),
      pw.Container(height: 1.5, color: _turuncu, margin: const pw.EdgeInsets.only(top: 6, bottom: 8)),
      pw.Row(mainAxisAlignment: pw.MainAxisAlignment.end, children: [
        pw.Text(borcEtiket, style: pw.TextStyle(fontSize: 11, fontWeight: pw.FontWeight.bold, color: _yazi)),
        pw.SizedBox(width: 10),
        pw.Text(para(v.bakiye.abs()), style: pw.TextStyle(fontSize: 17, fontWeight: pw.FontWeight.bold, color: _turuncu)),
      ]),
      pw.SizedBox(height: 12),
      pw.Text('Bu ekstre ${bugunGoster()} $saat tarihinde oluşturulmuştur.', style: const pw.TextStyle(fontSize: 8, color: _gri)),
      pw.SizedBox(height: 3),
      pw.Text('Bizi tercih ettiğiniz için teşekkür ederiz.  —  $firma', style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold, color: _koyu)),
    ],
  ));
  return belge.save();
}

/// PDF sayfalarını PNG yapar; alttaki boşluğu kırpar (WhatsApp'ta okunaklı olsun diye).
Future<List<Uint8List>> ekstrePng(Uint8List pdf) async {
  final sonuc = <Uint8List>[];
  await for (final s in Printing.raster(pdf, dpi: 150)) {
    final resim = img.Image.fromBytes(width: s.width, height: s.height, bytes: s.pixels.buffer, numChannels: 4, order: img.ChannelOrder.rgba);
    var alt = s.height - 1;
    bool bos(int y) {
      for (var x = 0; x < s.width; x += 3) {
        if (resim.getPixel(x, y).r < 250) return false;
      }
      return true;
    }

    while (alt > 0 && bos(alt)) {
      alt--;
    }
    final yukseklik = (alt + 45).clamp(1, s.height);
    sonuc.add(img.encodePng(img.copyCrop(resim, x: 0, y: 0, width: s.width, height: yukseklik), level: 4));
  }
  return sonuc;
}
