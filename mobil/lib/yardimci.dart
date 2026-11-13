import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

const firma = 'OĞUL TARIM';
const turuncu = Color(0xFFF17E01);
const koyuTuruncu = Color(0xFFC46400);
const acikTuruncu = Color(0xFFFEF2E6);
const zemin = Color(0xFFFBF8F5);
const kirmizi = Color(0xFFB00020);
const yesil = Color(0xFF1B7F2A);

/// 1234.5 -> '1.234,50 ₺'
String para(num x) {
  final s = x.abs().toStringAsFixed(2).split('.');
  final tam = s[0].replaceAllMapped(RegExp(r'\B(?=(\d{3})+$)'), (_) => '.');
  return '${x < -0.004 ? '-' : ''}$tam,${s[1]} ₺';
}

/// 3.0 -> '3', 2.5 -> '2,5'
String adetYaz(num x) {
  var s = x.toString();
  if (s.contains('.')) s = s.replaceFirst(RegExp(r'\.?0+$'), '');
  return s.replaceAll('.', ',');
}

/// '1.234,50' veya '1234.50' gibi girişleri sayıya çevirir; geçersizse null.
double? sayiOku(String metin) {
  var t = metin.trim().replaceAll(' ', '').replaceAll('₺', '');
  if (t.isEmpty) return null;
  if (t.contains(',')) t = t.replaceAll('.', '').replaceAll(',', '.');
  return double.tryParse(t);
}

/// 'GG.AA.YYYY' veya 'GG.AA.YY' -> 'YYYY-AA-GG'; geçersizse null.
String? tarihOku(String metin) {
  final m = RegExp(r'^(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})$').firstMatch(metin.trim());
  if (m == null) return null;
  final g = int.parse(m[1]!), a = int.parse(m[2]!);
  var y = int.parse(m[3]!);
  if (y < 100) y += 2000;
  final d = DateTime(y, a, g);
  if (d.year != y || d.month != a || d.day != g) return null;
  return tarihIso(d);
}

String tarihIso(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// 'YYYY-AA-GG' -> 'GG.AA.YYYY'
String tarihGoster(String iso) => '${iso.substring(8, 10)}.${iso.substring(5, 7)}.${iso.substring(0, 4)}';

String bugunGoster() => tarihGoster(tarihIso(DateTime.now()));

/// Türkçe uyumlu küçük harf (I->ı, İ->i).
String kucuk(String s) => s.replaceAll('I', 'ı').replaceAll('İ', 'i').toLowerCase();

/// Tarih kutusu: rakam yazdıkça noktalar kendiliğinden eklenir (06112026 -> 06.11.2026).
class TarihBicimi extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(TextEditingValue eski, TextEditingValue yeni) {
    var r = yeni.text.replaceAll(RegExp(r'\D'), '');
    if (r.length > 8) r = r.substring(0, 8);
    final ekliyor = yeni.text.length > eski.text.length;
    if (ekliyor && RegExp(r'[.,/\-]$').hasMatch(yeni.text) && (r.length == 1 || r.length == 3)) {
      r = '${r.substring(0, r.length - 1)}0${r[r.length - 1]}'; // 6. -> 06.
    }
    var m = r.substring(0, min(2, r.length));
    if (r.length > 2) m += '.${r.substring(2, min(4, r.length))}';
    if (r.length > 4) m += '.${r.substring(4)}';
    if (ekliyor && (r.length == 2 || r.length == 4)) m += '.';
    return TextEditingValue(text: m, selection: TextSelection.collapsed(offset: m.length));
  }
}

void mesajGoster(BuildContext context, String metin, {bool hata = false}) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(metin), backgroundColor: hata ? kirmizi : null));
}

Future<bool> onayla(BuildContext context, String baslik, String metin) async {
  final c = await showDialog<bool>(
    context: context,
    builder: (d) => AlertDialog(
      title: Text(baslik),
      content: Text(metin),
      actions: [
        TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('Vazgeç')),
        FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('Evet')),
      ],
    ),
  );
  return c ?? false;
}
