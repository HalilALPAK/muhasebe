import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'veritabani.dart';

const _api = 1;
const _gonderim = 400; // bir istekte en fazla bu kadar kayıt gider
/// Alpotech sunucusu; ayarlarda boşsa bu önerilir.
const varsayilanSunucu = 'https://muhasebe.l1bertech.com';
const internetMesaji = 'Sunucuya ulaşılamadı. İnternet bağlantınızı kontrol edin.';

class BulutHatasi implements Exception {
  final String mesaj;
  const BulutHatasi(this.mesaj);
  @override
  String toString() => mesaj;
}

class EsitlemeSonucu {
  final int gonderilen, alinan;
  final List<(int, int)> fisDegisen;
  const EsitlemeSonucu(this.gonderilen, this.alinan, this.fisDegisen);
}

Future<Map<String, dynamic>> _istek(http.Client c, String url, String anahtar, String yol, [Map<String, Object?>? govde]) async {
  final adres = Uri.parse('${url.replaceAll(RegExp(r'/+$'), '')}$yol');
  final basliklar = {'Authorization': 'Bearer $anahtar', 'Content-Type': 'application/json; charset=utf-8'};
  final http.Response y;
  try {
    y = await (govde == null ? c.get(adres, headers: basliklar) : c.post(adres, headers: basliklar, body: utf8.encode(jsonEncode(govde))))
        .timeout(const Duration(seconds: 60));
  } catch (_) {
    throw const BulutHatasi(internetMesaji);
  }
  Map<String, dynamic> cevap;
  try {
    cevap = jsonDecode(utf8.decode(y.bodyBytes)) as Map<String, dynamic>;
  } catch (_) {
    throw const BulutHatasi('Sunucudan geçersiz cevap geldi. Sunucu adresini kontrol edin.');
  }
  if (y.statusCode == 401) throw const BulutHatasi('Sunucu anahtarı hatalı. Sunucu ayarlarını kontrol edin.');
  if (y.statusCode != 200) throw BulutHatasi((cevap['hata'] as String?) ?? 'Sunucu hatası (${y.statusCode})');
  return cevap;
}

Future<Map<String, dynamic>> durumSor(String url, String anahtar, {http.Client? istemci}) async {
  final c = istemci ?? http.Client();
  try {
    final d = await _istek(c, url, anahtar, '/v1/durum');
    if (d['uygulama'] != 'ogul_tarim') throw const BulutHatasi('Bu adres Oğul Tarım sunucusu değil.');
    return d;
  } finally {
    if (istemci == null) c.close();
  }
}

/// Bekleyen değişiklikleri parça parça gönderir, sunucudaki yenileri alır.
Future<EsitlemeSonucu> esitle(Veritabani vt, String url, String anahtar, String cihaz, {http.Client? istemci}) async {
  final c = istemci ?? http.Client();
  var gonderilen = 0, alinan = 0;
  final fisDegisen = <(int, int)>[];
  try {
    for (var tur = 0; tur < 500; tur++) {
      final son = int.tryParse(await vt.ayar('son_surum', '0')) ?? 0;
      final (giden, isaret) = await vt.kirlileriTopla(_gonderim);
      final cevap = await _istek(c, url, anahtar, '/v1/esitle', {'api': _api, 'cihaz': cihaz, 'son_surum': son, 'degisiklikler': giden});
      if (cevap['sunucu_sifirlandi'] == true) {
        await vt.hepsiniGonderilecekYap(); // sunucu verisi silinmiş: bu cihazdaki her şey yeniden yüklenir
        continue;
      }
      final yerelDegisen = <(int, int)>[];
      try {
        alinan += await vt.uygula(cevap, isaret, yerelDegisen);
      } on StateError catch (e) {
        throw BulutHatasi(e.message);
      }
      gonderilen += isaret.length;
      fisDegisen
        ..addAll([for (final f in (cevap['rapor'] as Map)['fis_degisen'] as List) (f['eski'] as int, f['yeni'] as int)])
        ..addAll(yerelDegisen);
      if (isaret.isEmpty && cevap['daha_var'] != true) break;
    }
    await vt.ayarYaz('son_esitleme', DateTime.now().toIso8601String());
    return EsitlemeSonucu(gonderilen, alinan, fisDegisen);
  } finally {
    if (istemci == null) c.close();
  }
}

/// Değişiklikten birkaç saniye sonra, uygulama açılınca ve her dakika arka planda eşitler.
class BulutEsitleyici {
  final Veritabani vt;
  final durum = ValueNotifier<String>('');
  final hata = ValueNotifier<bool>(false);
  Timer? _gecikme, _periyot;
  bool _calisiyor = false, _bekleyen = false;

  BulutEsitleyici(this.vt);

  void baslat() {
    vt.yerelDegisti.addListener(() => tetikle(const Duration(seconds: 3)));
    _periyot = Timer.periodic(const Duration(minutes: 1), (_) => tetikle());
    tetikle();
  }

  void durdur() {
    _gecikme?.cancel();
    _periyot?.cancel();
  }

  void tetikle([Duration gecikme = Duration.zero]) {
    _gecikme?.cancel();
    _gecikme = Timer(gecikme, () => simdi().catchError((Object _) => const EsitlemeSonucu(0, 0, [])));
  }

  Future<bool> ayarli() async => (await vt.ayar('sunucu_url')).isNotEmpty && (await vt.ayar('sunucu_anahtar')).isNotEmpty;

  /// Hemen eşitler; hata olursa [BulutHatasi] fırlatır (durum yazısı da güncellenir).
  Future<EsitlemeSonucu> simdi() async {
    if (_calisiyor) {
      _bekleyen = true;
      return const EsitlemeSonucu(0, 0, []);
    }
    if (!await ayarli()) {
      hata.value = true;
      durum.value = 'Sunucu ayarlanmadı';
      throw const BulutHatasi('Önce sunucu adresini ve anahtarını girin.');
    }
    _calisiyor = true;
    durum.value = 'Eşitleniyor…';
    try {
      final s = await esitle(vt, await vt.ayar('sunucu_url'), await vt.ayar('sunucu_anahtar'), await vt.ayar('cihaz', 'telefon'));
      final b = await vt.bekleyenSayisi();
      final n = DateTime.now();
      hata.value = false;
      durum.value = 'Eşitlendi ${n.hour.toString().padLeft(2, '0')}:${n.minute.toString().padLeft(2, '0')}'
          '${b > 0 ? ' · $b bekleyen' : ''}'
          '${s.fisDegisen.isNotEmpty ? ' · ${s.fisDegisen.map((f) => 'Fiş ${f.$1}→${f.$2}').join(', ')}' : ''}';
      return s;
    } on BulutHatasi catch (e) {
      final b = await vt.bekleyenSayisi();
      hata.value = true;
      durum.value = e.mesaj == internetMesaji ? 'Çevrimdışı · $b bekleyen' : e.mesaj;
      rethrow;
    } finally {
      _calisiyor = false;
      if (_bekleyen) {
        _bekleyen = false;
        tetikle(const Duration(milliseconds: 500));
      }
    }
  }
}
