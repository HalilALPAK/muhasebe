import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

import '../yardimci.dart';

class Kalem {
  final String urun;
  final double adet;
  final double fiyat;
  const Kalem(this.urun, this.adet, this.fiyat);
  double get tutar => adet * fiyat;
}

class MusteriOzet {
  final String uuid, ad, telefon;
  final double devir, satis, tahsilat;
  const MusteriOzet(this.uuid, this.ad, this.telefon, this.devir, this.satis, this.tahsilat);
  double get bakiye => devir + satis - tahsilat;
}

class Musteri {
  final String uuid, ad, telefon, notlar;
  const Musteri(this.uuid, this.ad, this.telefon, this.notlar);
}

class Islem {
  final String uuid, musteriUuid, musteriAd, tur, tarih, aciklama;
  final double tutar;
  final int? fisNo;
  final List<Kalem> kalemler;
  const Islem(this.uuid, this.musteriUuid, this.musteriAd, this.tur, this.tarih, this.tutar, this.aciklama, this.fisNo,
      this.kalemler);
  bool get satis => tur == satisTur;
}

class Gider {
  final String uuid, tarih, kategori, aciklama;
  final double tutar;
  const Gider(this.uuid, this.tarih, this.kategori, this.tutar, this.aciklama);
}

const satisTur = 'SATIŞ';
const tahsilatTur = 'TAHSİLAT';
const varsayilanGiderler = ['Kira', 'Elektrik', 'Su', 'Doğalgaz', 'Maaş', 'Mal Alımı', 'Yakıt', 'Vergi', 'İnternet / Telefon', 'Diğer'];

String _yeniId() {
  final r = Random.secure();
  return List.generate(16, (_) => r.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
}

int _simdi() => DateTime.now().millisecondsSinceEpoch;

double _d(Object? v) => (v as num?)?.toDouble() ?? 0;

/// Telefondaki veritabanı. Hesaplar laptop programıyla aynıdır; her yazma işlemi kayda kimlik ve
/// değişiklik zamanı basar, silinenler [silinen] tablosuna yazılır ki eşitlemede geri gelmesin.
class Veritabani {
  final Database db;

  /// Veri her değiştiğinde artar; ekranlar bunu dinleyip kendini yeniler.
  final degisti = ValueNotifier<int>(0);

  Veritabani._(this.db);

  static Future<Veritabani> ac({DatabaseFactory? fabrika, String? yol}) async {
    final f = fabrika ?? databaseFactory;
    final dosya = yol ?? p.join(await f.getDatabasesPath(), 'muhasebe.db');
    final db = await f.openDatabase(dosya, options: OpenDatabaseOptions(version: 2, onCreate: _olustur, onUpgrade: _yukselt));
    return Veritabani._(db);
  }

  static Future<void> _olustur(Database d, int _) async {
    await d.execute('CREATE TABLE musteri (uuid TEXT PRIMARY KEY, ad TEXT NOT NULL, telefon TEXT DEFAULT \'\', '
        'notlar TEXT DEFAULT \'\', guncelleme INTEGER NOT NULL)');
    await d.execute('CREATE TABLE islem (uuid TEXT PRIMARY KEY, musteri_uuid TEXT NOT NULL, tur TEXT NOT NULL, '
        'tarih TEXT NOT NULL, tutar REAL NOT NULL, aciklama TEXT DEFAULT \'\', fis_no INTEGER, guncelleme INTEGER NOT NULL)');
    await d.execute('CREATE INDEX islem_musteri ON islem(musteri_uuid)');
    await d.execute('CREATE TABLE kalem (id INTEGER PRIMARY KEY AUTOINCREMENT, islem_uuid TEXT NOT NULL, urun TEXT NOT NULL, '
        'adet REAL NOT NULL, birim_fiyat REAL NOT NULL)');
    await d.execute('CREATE INDEX kalem_islem ON kalem(islem_uuid)');
    await d.execute('CREATE TABLE gider (uuid TEXT PRIMARY KEY, tarih TEXT NOT NULL, kategori TEXT DEFAULT \'\', '
        'tutar REAL NOT NULL, aciklama TEXT DEFAULT \'\', guncelleme INTEGER NOT NULL)');
    await d.execute('CREATE TABLE silinen (uuid TEXT PRIMARY KEY, tablo TEXT NOT NULL, zaman INTEGER NOT NULL)');
    await d.execute('CREATE TABLE ayar (anahtar TEXT PRIMARY KEY, deger TEXT)');
    await _yukselt(d, 1, 2);
  }

  /// Sürüm 2: 'kirli' = sunucuya henüz gönderilmedi. Mevcut kayıtlar 1 ile başlar, ilk eşitlemede yüklenir.
  static Future<void> _yukselt(Database d, int eski, int yeni) async {
    if (eski < 2) {
      for (final t in ['musteri', 'islem', 'gider', 'silinen']) {
        await d.execute('ALTER TABLE $t ADD COLUMN kirli INTEGER NOT NULL DEFAULT 1');
      }
    }
  }

  /// Sadece bu cihazda yapılan değişikliklerde artar (eşitleyici bunu dinleyip gönderir).
  final yerelDegisti = ValueNotifier<int>(0);

  void _haberVer({bool yerel = true}) {
    degisti.value++;
    if (yerel) yerelDegisti.value++;
  }

  (String, String) _aralik(int? yil) => yil != null ? ('$yil-01-01', '$yil-12-31') : ('0000-01-01', '9999-12-31');

  Future<double> _tek(String sql, [List<Object?>? a]) async => _d((await db.rawQuery(sql, a)).first.values.first);

  // --- müşteri
  Future<List<MusteriOzet>> musteriler({String ara = '', int? yil}) async {
    final q = kucuk(ara);
    final (bas, bit) = _aralik(yil);
    final satirlar = await db.rawQuery('''
      SELECT m.uuid, m.ad, m.telefon,
        COALESCE(SUM(CASE WHEN i.tarih < ? THEN (CASE WHEN i.tur='SATIŞ' THEN i.tutar ELSE -i.tutar END) END), 0) devir,
        COALESCE(SUM(CASE WHEN i.tur='SATIŞ' AND i.tarih BETWEEN ? AND ? THEN i.tutar END), 0) satis,
        COALESCE(SUM(CASE WHEN i.tur='TAHSİLAT' AND i.tarih BETWEEN ? AND ? THEN i.tutar END), 0) tahsilat,
        COUNT(i.uuid) toplam,
        COALESCE(SUM(CASE WHEN i.tarih BETWEEN ? AND ? THEN 1 END), 0) yil_adet
      FROM musteri m LEFT JOIN islem i ON i.musteri_uuid = m.uuid
      GROUP BY m.uuid ORDER BY m.ad COLLATE NOCASE
    ''', [bas, bas, bit, bas, bit, bas, bit]);
    return [
      for (final s in satirlar)
        if (kucuk(s['ad'] as String).contains(q) &&
            (q.isNotEmpty || s['toplam'] == 0 || (s['yil_adet'] as int) > 0 || _d(s['devir']).abs() > 0.005))
          MusteriOzet(s['uuid'] as String, s['ad'] as String, (s['telefon'] as String?) ?? '', _d(s['devir']),
              _d(s['satis']), _d(s['tahsilat'])),
    ];
  }

  Future<Musteri?> musteri(String uuid) async {
    final r = await db.query('musteri', where: 'uuid = ?', whereArgs: [uuid]);
    if (r.isEmpty) return null;
    return Musteri(uuid, r.first['ad'] as String, (r.first['telefon'] as String?) ?? '', (r.first['notlar'] as String?) ?? '');
  }

  Future<List<String>> musteriAdlari() async =>
      [for (final r in await db.rawQuery('SELECT ad FROM musteri ORDER BY ad COLLATE NOCASE')) r['ad'] as String];

  /// Adı (büyük/küçük harf farkı gözetmeden) birebir eşleşen müşterinin kimliği.
  Future<String?> musteriBul(String ad) async {
    final q = kucuk(ad.trim());
    for (final r in await db.query('musteri', columns: ['uuid', 'ad'])) {
      if (kucuk((r['ad'] as String).trim()) == q) return r['uuid'] as String;
    }
    return null;
  }

  Future<String> musteriKaydet({String? uuid, required String ad, String telefon = '', String notlar = ''}) async {
    final id = uuid ?? _yeniId();
    await db.insert('musteri', {'uuid': id, 'ad': ad, 'telefon': telefon, 'notlar': notlar, 'guncelleme': _simdi(), 'kirli': 1},
        conflictAlgorithm: ConflictAlgorithm.replace);
    _haberVer();
    return id;
  }

  Future<void> musteriSil(String uuid) async {
    final z = _simdi();
    await db.transaction((t) async {
      for (final r in await t.query('islem', columns: ['uuid'], where: 'musteri_uuid = ?', whereArgs: [uuid])) {
        await _islemSil(t, r['uuid'] as String, z);
      }
      await t.delete('musteri', where: 'uuid = ?', whereArgs: [uuid]);
      await t.insert('silinen', {'uuid': uuid, 'tablo': 'musteri', 'zaman': z, 'kirli': 1}, conflictAlgorithm: ConflictAlgorithm.replace);
    });
    _haberVer();
  }

  // --- işlemler
  Future<Map<String, List<Kalem>>> _kalemler(List<Object?> ids) async {
    final m = <String, List<Kalem>>{};
    if (ids.isEmpty) return m;
    for (var i = 0; i < ids.length; i += 400) {
      final parca = ids.sublist(i, min(i + 400, ids.length));
      final r = await db.query('kalem', where: 'islem_uuid IN (${List.filled(parca.length, '?').join(',')})', whereArgs: parca, orderBy: 'id');
      for (final k in r) {
        m.putIfAbsent(k['islem_uuid'] as String, () => []).add(Kalem(k['urun'] as String, _d(k['adet']), _d(k['birim_fiyat'])));
      }
    }
    return m;
  }

  Future<List<Islem>> _islemlereCevir(List<Map<String, Object?>> s) async {
    final k = await _kalemler([for (final r in s) if (r['tur'] == satisTur) r['uuid']]);
    return [
      for (final r in s)
        Islem(r['uuid'] as String, r['musteri_uuid'] as String, (r['ad'] as String?) ?? '', r['tur'] as String, r['tarih'] as String,
            _d(r['tutar']), (r['aciklama'] as String?) ?? '', r['fis_no'] as int?, k[r['uuid']] ?? const []),
    ];
  }

  Future<List<Islem>> islemler(String musteriUuid, {int? yil}) async {
    final (bas, bit) = _aralik(yil);
    return _islemlereCevir(await db.rawQuery('''
      SELECT i.*, m.ad FROM islem i JOIN musteri m ON m.uuid = i.musteri_uuid
      WHERE i.musteri_uuid = ? AND i.tarih BETWEEN ? AND ? ORDER BY i.tarih, i.rowid''', [musteriUuid, bas, bit]));
  }

  /// Girilme sırasına göre son işlemler (en yeni önce).
  Future<List<Islem>> sonIslemler({int adet = 300, String? musteriUuid}) async {
    final f = musteriUuid != null ? 'WHERE i.musteri_uuid = ?' : '';
    return _islemlereCevir(await db.rawQuery('''
      SELECT i.*, m.ad FROM islem i JOIN musteri m ON m.uuid = i.musteri_uuid $f ORDER BY i.rowid DESC LIMIT ?''',
        [if (musteriUuid != null) musteriUuid, adet]));
  }

  Future<Islem?> islem(String uuid) async {
    final l = await _islemlereCevir(
        await db.rawQuery('SELECT i.*, m.ad FROM islem i JOIN musteri m ON m.uuid = i.musteri_uuid WHERE i.uuid = ?', [uuid]));
    return l.isEmpty ? null : l.first;
  }

  Future<double> devir(String musteriUuid, int yil) => _tek(
      "SELECT COALESCE(SUM(CASE WHEN tur='SATIŞ' THEN tutar ELSE -tutar END), 0) FROM islem WHERE musteri_uuid = ? AND tarih < ?",
      [musteriUuid, '$yil-01-01']);

  Future<int> sonrakiFisNo() async => (await _tek('SELECT COALESCE(MAX(fis_no), 0) + 1 FROM islem')).toInt();

  /// Bu fiş numarası başka bir satışta kullanılıyorsa 'müşteri, tarih' döner.
  Future<String?> fisKullanan(int no, String? haric) async {
    final r = await db.rawQuery('''SELECT m.ad, i.tarih FROM islem i JOIN musteri m ON m.uuid = i.musteri_uuid
       WHERE i.fis_no = ? AND i.uuid IS NOT ?''', [no, haric]);
    return r.isEmpty ? null : '${r.first['ad']}, ${tarihGoster(r.first['tarih'] as String)}';
  }

  Future<List<String>> urunAdlari() async =>
      [for (final r in await db.rawQuery('SELECT urun FROM kalem GROUP BY urun ORDER BY COUNT(*) DESC, urun')) r['urun'] as String];

  Future<double?> sonFiyat(String urun) async {
    final r = await db.rawQuery('''SELECT k.birim_fiyat FROM kalem k JOIN islem i ON i.uuid = k.islem_uuid
       WHERE k.urun = ? ORDER BY i.tarih DESC, k.id DESC LIMIT 1''', [urun]);
    return r.isEmpty ? null : _d(r.first['birim_fiyat']);
  }

  Future<void> satisKaydet({String? uuid, required String musteriUuid, required String tarih, required List<Kalem> kalemler, String aciklama = '', required int fisNo}) async {
    final id = uuid ?? _yeniId();
    final toplam = (kalemler.fold<double>(0, (t, k) => t + k.tutar) * 100).round() / 100;
    final veri = {'musteri_uuid': musteriUuid, 'tur': satisTur, 'tarih': tarih, 'tutar': toplam, 'aciklama': aciklama, 'fis_no': fisNo, 'guncelleme': _simdi(), 'kirli': 1};
    await db.transaction((t) async {
      if (uuid != null) {
        await t.update('islem', veri, where: 'uuid = ?', whereArgs: [uuid]);
        await t.delete('kalem', where: 'islem_uuid = ?', whereArgs: [uuid]);
      } else {
        await t.insert('islem', {'uuid': id, ...veri});
      }
      for (final k in kalemler) {
        await t.insert('kalem', {'islem_uuid': id, 'urun': k.urun, 'adet': k.adet, 'birim_fiyat': k.fiyat});
      }
    });
    _haberVer();
  }

  Future<void> tahsilatKaydet({String? uuid, required String musteriUuid, required String tarih, required double tutar, String aciklama = ''}) async {
    final veri = {'musteri_uuid': musteriUuid, 'tur': tahsilatTur, 'tarih': tarih, 'tutar': tutar, 'aciklama': aciklama, 'guncelleme': _simdi(), 'kirli': 1};
    if (uuid != null) {
      await db.update('islem', veri, where: 'uuid = ?', whereArgs: [uuid]);
    } else {
      await db.insert('islem', {'uuid': _yeniId(), ...veri});
    }
    _haberVer();
  }

  Future<void> _islemSil(DatabaseExecutor t, String uuid, int z) async {
    await t.delete('kalem', where: 'islem_uuid = ?', whereArgs: [uuid]);
    await t.delete('islem', where: 'uuid = ?', whereArgs: [uuid]);
    await t.insert('silinen', {'uuid': uuid, 'tablo': 'islem', 'zaman': z, 'kirli': 1}, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> islemSil(String uuid) async {
    await db.transaction((t) => _islemSil(t, uuid, _simdi()));
    _haberVer();
  }

  // --- gider
  Future<List<Gider>> giderler(String bas, String bit) async => [
        for (final r in await db.query('gider', where: 'tarih BETWEEN ? AND ?', whereArgs: [bas, bit], orderBy: 'tarih, rowid'))
          Gider(r['uuid'] as String, r['tarih'] as String, (r['kategori'] as String?) ?? '', _d(r['tutar']), (r['aciklama'] as String?) ?? ''),
      ];

  Future<List<String>> giderKategorileri() async {
    final k = [
      for (final r in await db.rawQuery("SELECT kategori FROM gider WHERE kategori <> '' GROUP BY kategori ORDER BY COUNT(*) DESC")) r['kategori'] as String
    ];
    return [...k, ...varsayilanGiderler.where((v) => !k.contains(v))];
  }

  Future<void> giderEkle(String tarih, String kategori, double tutar, String aciklama) async {
    await db.insert('gider', {'uuid': _yeniId(), 'tarih': tarih, 'kategori': kategori, 'tutar': tutar, 'aciklama': aciklama, 'guncelleme': _simdi(), 'kirli': 1});
    _haberVer();
  }

  Future<void> giderSil(String uuid) async {
    await db.transaction((t) async {
      await t.delete('gider', where: 'uuid = ?', whereArgs: [uuid]);
      await t.insert('silinen', {'uuid': uuid, 'tablo': 'gider', 'zaman': _simdi(), 'kirli': 1}, conflictAlgorithm: ConflictAlgorithm.replace);
    });
    _haberVer();
  }

  // --- raporlar
  Future<List<int>> yillar() async {
    final r = await db.rawQuery('SELECT DISTINCT substr(tarih, 1, 4) y FROM islem UNION SELECT DISTINCT substr(tarih, 1, 4) FROM gider');
    final y = {DateTime.now().year, for (final s in r) int.parse(s['y'] as String)};
    final enBuyuk = y.reduce(max), enKucuk = y.reduce(min);
    return [for (var i = enBuyuk; i >= enKucuk; i--) i];
  }

  Future<String?> ilkTarih() async {
    final r = await db.rawQuery('SELECT MIN(t) t FROM (SELECT MIN(tarih) t FROM islem UNION ALL SELECT MIN(tarih) FROM gider)');
    return r.first['t'] as String?;
  }

  Future<Map<String, double>> ozet(String bas, String bit) async {
    final s = (await db.rawQuery("SELECT COUNT(*) n, COALESCE(SUM(tutar), 0) t FROM islem WHERE tur='SATIŞ' AND tarih BETWEEN ? AND ?", [bas, bit])).first;
    return {
      'satis_sayisi': _d(s['n']),
      'ciro': _d(s['t']),
      'tahsilat': await _tek("SELECT COALESCE(SUM(tutar), 0) FROM islem WHERE tur='TAHSİLAT' AND tarih BETWEEN ? AND ?", [bas, bit]),
      'gider': await _tek('SELECT COALESCE(SUM(tutar), 0) FROM gider WHERE tarih BETWEEN ? AND ?', [bas, bit]),
      'urun_adedi': await _tek('SELECT COALESCE(SUM(k.adet), 0) FROM kalem k JOIN islem i ON i.uuid = k.islem_uuid WHERE i.tarih BETWEEN ? AND ?', [bas, bit]),
      'alacak': await _tek("SELECT COALESCE(SUM(CASE WHEN tur='SATIŞ' THEN tutar ELSE -tutar END), 0) FROM islem WHERE tarih <= ?", [bit]),
    };
  }

  /// [(dönem, satış, tahsilat, gider)] gün veya ay bazında, eskiden yeniye.
  Future<List<(String, double, double, double)>> donemDokumu(String bas, String bit, bool aylik) async {
    final a = aylik ? 'substr(tarih, 1, 7)' : 'tarih';
    final v = <String, List<double>>{};
    for (final r in await db.rawQuery('SELECT $a k, tur, SUM(tutar) t FROM islem WHERE tarih BETWEEN ? AND ? GROUP BY 1, 2', [bas, bit])) {
      v.putIfAbsent(r['k'] as String, () => [0, 0, 0])[r['tur'] == satisTur ? 0 : 1] += _d(r['t']);
    }
    for (final r in await db.rawQuery('SELECT $a k, SUM(tutar) t FROM gider WHERE tarih BETWEEN ? AND ? GROUP BY 1', [bas, bit])) {
      v.putIfAbsent(r['k'] as String, () => [0, 0, 0])[2] += _d(r['t']);
    }
    final anahtar = v.keys.toList()..sort();
    return [for (final k in anahtar) (k, v[k]![0], v[k]![1], v[k]![2])];
  }

  /// [(ürün, adet, satış sayısı, ciro)] ciroya göre.
  Future<List<(String, double, int, double)>> urunRaporu(String bas, String bit) async => [
        for (final r in await db.rawQuery('''SELECT k.urun, SUM(k.adet) a, COUNT(DISTINCT k.islem_uuid) n, SUM(k.adet * k.birim_fiyat) c
            FROM kalem k JOIN islem i ON i.uuid = k.islem_uuid WHERE i.tarih BETWEEN ? AND ? GROUP BY k.urun ORDER BY 4 DESC''', [bas, bit]))
          (r['urun'] as String, _d(r['a']), r['n'] as int, _d(r['c'])),
      ];

  /// [(müşteri uuid, ad, satış, tahsilat, bitişteki bakiye)]
  Future<List<(String, String, double, double, double)>> musteriRaporu(String bas, String bit) async => [
        for (final r in await db.rawQuery('''SELECT m.uuid, m.ad,
              SUM(CASE WHEN i.tur='SATIŞ' AND i.tarih BETWEEN ? AND ? THEN i.tutar ELSE 0 END) s,
              SUM(CASE WHEN i.tur='TAHSİLAT' AND i.tarih BETWEEN ? AND ? THEN i.tutar ELSE 0 END) t,
              SUM(CASE WHEN i.tarih <= ? THEN (CASE WHEN i.tur='SATIŞ' THEN i.tutar ELSE -i.tutar END) ELSE 0 END) b
            FROM musteri m JOIN islem i ON i.musteri_uuid = m.uuid GROUP BY m.uuid ORDER BY 3 DESC, 4 DESC''', [bas, bit, bas, bit, bit]))
          if (_d(r['s']) != 0 || _d(r['t']) != 0) (r['uuid'] as String, r['ad'] as String, _d(r['s']), _d(r['t']), _d(r['b'])),
      ];

  // --- eşitleme (kurallar sunucuda; burada gönderilecekleri toplayıp gelenleri uygularız)
  Future<String> ayar(String anahtar, [String varsayilan = '']) async {
    final r = await db.query('ayar', where: 'anahtar = ?', whereArgs: [anahtar]);
    return r.isEmpty ? varsayilan : (r.first['deger'] as String? ?? varsayilan);
  }

  Future<void> ayarYaz(String anahtar, String deger) =>
      db.insert('ayar', {'anahtar': anahtar, 'deger': deger}, conflictAlgorithm: ConflictAlgorithm.replace);

  Future<int> bekleyenSayisi() async {
    var n = 0;
    for (final t in ['musteri', 'islem', 'gider', 'silinen']) {
      n += (await _tek('SELECT COUNT(*) FROM $t WHERE kirli = 1')).toInt();
    }
    return n;
  }

  /// Yeni sunucu: her şey baştan gönderilip alınır.
  Future<void> hepsiniGonderilecekYap() async {
    for (final t in ['musteri', 'islem', 'gider', 'silinen']) {
      await db.update(t, {'kirli': 1});
    }
    await ayarYaz('son_surum', '0');
  }

  /// Gönderilecek kayıtlar (müşteriler önce, sonra işlem/gider, en son silmeler) ve
  /// gönderim sonrası işaretlerini kaldırmak için (tablo, uuid, zaman) listesi.
  Future<(Map<String, List<Map<String, Object?>>>, List<(String, String, int)>)> kirlileriTopla(int sinir) async {
    final d = <String, List<Map<String, Object?>>>{'musteri': [], 'islem': [], 'gider': [], 'silinen': []};
    final isaret = <(String, String, int)>[];
    for (final m in await db.query('musteri', where: 'kirli = 1', limit: sinir)) {
      d['musteri']!.add({'uuid': m['uuid'], 'ad': m['ad'], 'telefon': m['telefon'] ?? '', 'notlar': m['notlar'] ?? '', 'guncelleme': m['guncelleme']});
      isaret.add(('musteri', m['uuid'] as String, m['guncelleme'] as int));
    }
    if (d['musteri']!.isNotEmpty) return (d, isaret);
    final islemler = await db.query('islem', where: 'kirli = 1', limit: sinir);
    final k = await _kalemler([for (final i in islemler) i['uuid']]);
    for (final i in islemler) {
      d['islem']!.add({
        'uuid': i['uuid'], 'musteri_uuid': i['musteri_uuid'], 'tur': i['tur'], 'tarih': i['tarih'], 'tutar': _d(i['tutar']),
        'aciklama': i['aciklama'] ?? '', 'fis_no': i['fis_no'], 'guncelleme': i['guncelleme'],
        'kalemler': [for (final x in k[i['uuid']] ?? const <Kalem>[]) {'urun': x.urun, 'adet': x.adet, 'birim_fiyat': x.fiyat}],
      });
      isaret.add(('islem', i['uuid'] as String, i['guncelleme'] as int));
    }
    for (final g in await db.query('gider', where: 'kirli = 1', limit: max(sinir - isaret.length, 0))) {
      d['gider']!.add({'uuid': g['uuid'], 'tarih': g['tarih'], 'kategori': g['kategori'] ?? '', 'tutar': _d(g['tutar']), 'aciklama': g['aciklama'] ?? '', 'guncelleme': g['guncelleme']});
      isaret.add(('gider', g['uuid'] as String, g['guncelleme'] as int));
    }
    if (d['islem']!.isEmpty) {
      for (final s in await db.query('silinen', where: 'kirli = 1', limit: max(sinir - isaret.length, 0))) {
        d['silinen']!.add({'uuid': s['uuid'], 'tablo': s['tablo'], 'zaman': s['zaman']});
        isaret.add(('silinen', s['uuid'] as String, s['zaman'] as int));
      }
    }
    return (d, isaret);
  }

  /// Sunucu cevabını tek işlemde uygular. Gelenler 'kirli' sayılmaz; yerelde daha yeni ve henüz
  /// gönderilmemiş bir değişiklik varsa o korunur (sonraki eşitlemede gider).
  Future<int> uygula(Map<String, dynamic> c, List<(String, String, int)> isaret, List<(int, int)> fisDegisen) async {
    var alinan = 0;
    await db.transaction((t) async {
      for (final (tablo, uuid, z) in isaret) {
        await t.rawUpdate('UPDATE $tablo SET kirli = 0 WHERE uuid = ? AND ${tablo == 'silinen' ? 'zaman' : 'guncelleme'} = ? AND kirli = 1', [uuid, z]);
      }
      Future<Map<String, Object?>?> satir(String tablo, String uuid) async {
        final r = await t.query(tablo, columns: ['guncelleme', 'kirli'], where: 'uuid = ?', whereArgs: [uuid]);
        return r.isEmpty ? null : r.first;
      }

      bool yerelDahaYeni(Map<String, Object?>? r, Map s) => r != null && r['kirli'] == 1 && (r['guncelleme'] as int) > (s['guncelleme'] as int);
      Future<void> iz(String uuid, String tablo, int z) =>
          t.insert('silinen', {'uuid': uuid, 'tablo': tablo, 'zaman': z, 'kirli': 0}, conflictAlgorithm: ConflictAlgorithm.replace);

      for (final m in [...c['musteri'] as List, ...(c['bagli_musteri'] as List? ?? const [])]) {
        final r = await satir('musteri', m['uuid']);
        if (yerelDahaYeni(r, m)) continue;
        alinan++;
        if (m['silindi'] == 1) {
          if (r != null) {
            if ((await t.query('islem', where: 'musteri_uuid = ? AND kirli = 1', whereArgs: [m['uuid']], limit: 1)).isNotEmpty) continue;
            for (final i in await t.query('islem', columns: ['uuid'], where: 'musteri_uuid = ?', whereArgs: [m['uuid']])) {
              await _islemSil(t, i['uuid'] as String, m['guncelleme'] as int);
              await iz(i['uuid'] as String, 'islem', m['guncelleme'] as int);
            }
            await t.delete('musteri', where: 'uuid = ?', whereArgs: [m['uuid']]);
          }
          await iz(m['uuid'], 'musteri', m['guncelleme']);
        } else {
          await t.delete('silinen', where: 'uuid = ?', whereArgs: [m['uuid']]);
          final v = {'ad': m['ad'], 'telefon': m['telefon'], 'notlar': m['notlar'], 'guncelleme': m['guncelleme'], 'kirli': 0};
          if (r != null) {
            await t.update('musteri', v, where: 'uuid = ?', whereArgs: [m['uuid']]);
          } else {
            await t.insert('musteri', {'uuid': m['uuid'], ...v});
          }
        }
      }

      final esleme = {for (final e in c['esleme'] as List? ?? const []) e['eski'] as String: e['yeni'] as String};
      for (final e in esleme.entries) {
        // sunucuda aynı isimli müşterilerle birleştirilenler
        if (await satir('musteri', e.key) != null && await satir('musteri', e.value) != null) {
          await t.update('islem', {'musteri_uuid': e.value}, where: 'musteri_uuid = ?', whereArgs: [e.key]);
          await t.delete('musteri', where: 'uuid = ?', whereArgs: [e.key]);
        }
      }

      final uygulanacak = <(Map, Map<String, Object?>?)>[];
      for (final s in c['islem'] as List) {
        final r = await satir('islem', s['uuid']);
        if (!yerelDahaYeni(r, s)) uygulanacak.add((s as Map, r));
      }
      for (final (s, r) in uygulanacak) {
        if (r != null) await t.update('islem', {'fis_no': null}, where: 'uuid = ?', whereArgs: [s['uuid']]);
      }
      for (final (s, r) in uygulanacak) {
        alinan++;
        if (s['silindi'] == 1) {
          await _islemSil(t, s['uuid'], s['guncelleme']);
          await iz(s['uuid'], 'islem', s['guncelleme']);
          continue;
        }
        var mu = s['musteri_uuid'] as String;
        for (var n = 0; n < 10 && esleme.containsKey(mu); n++) {
          mu = esleme[mu]!;
        }
        if (await satir('musteri', mu) == null) throw StateError('Sunucudan gelen bir işlemin müşterisi bulunamadı. Tekrar eşitleyin.');
        final fis = s['fis_no'] as int?;
        if (fis != null) {
          final cakisan = await t.query('islem', columns: ['uuid'], where: 'fis_no = ? AND uuid <> ?', whereArgs: [fis, s['uuid']]);
          if (cakisan.isNotEmpty) {
            // yerelde aynı numaralı, henüz gönderilmemiş fiş: ona yeni numara
            final yeni = (await t.rawQuery('SELECT COALESCE(MAX(fis_no), 0) + 1 n FROM islem')).first['n'] as int;
            await t.update('islem', {'fis_no': yeni}, where: 'uuid = ?', whereArgs: [cakisan.first['uuid']]);
            fisDegisen.add((fis, yeni));
          }
        }
        await t.delete('silinen', where: 'uuid = ?', whereArgs: [s['uuid']]);
        await t.delete('kalem', where: 'islem_uuid = ?', whereArgs: [s['uuid']]);
        final v = {
          'musteri_uuid': mu, 'tur': s['tur'], 'tarih': s['tarih'], 'tutar': _d(s['tutar']), 'aciklama': s['aciklama'],
          'fis_no': fis, 'guncelleme': s['guncelleme'], 'kirli': 0,
        };
        if (r != null) {
          await t.update('islem', v, where: 'uuid = ?', whereArgs: [s['uuid']]); // girilme sırası korunur
        } else {
          await t.insert('islem', {'uuid': s['uuid'], ...v});
        }
        for (final k in s['kalemler'] as List) {
          await t.insert('kalem', {'islem_uuid': s['uuid'], 'urun': k['urun'], 'adet': _d(k['adet']), 'birim_fiyat': _d(k['birim_fiyat'])});
        }
      }

      for (final x in c['gider'] as List) {
        final r = await satir('gider', x['uuid']);
        if (yerelDahaYeni(r, x)) continue;
        alinan++;
        if (x['silindi'] == 1) {
          await t.delete('gider', where: 'uuid = ?', whereArgs: [x['uuid']]);
          await iz(x['uuid'], 'gider', x['guncelleme']);
        } else {
          await t.delete('silinen', where: 'uuid = ?', whereArgs: [x['uuid']]);
          await t.insert('gider', {'uuid': x['uuid'], 'tarih': x['tarih'], 'kategori': x['kategori'], 'tutar': _d(x['tutar']), 'aciklama': x['aciklama'], 'guncelleme': x['guncelleme'], 'kirli': 0},
              conflictAlgorithm: ConflictAlgorithm.replace);
        }
      }
      await t.insert('ayar', {'anahtar': 'son_surum', 'deger': '${c['son_surum']}'}, conflictAlgorithm: ConflictAlgorithm.replace);
    });
    if (alinan > 0) _haberVer(yerel: false);
    return alinan;
  }

  Future<DateTime?> sonEsitleme() async {
    final r = await db.query('ayar', where: 'anahtar = ?', whereArgs: ['son_esitleme']);
    return r.isEmpty ? null : DateTime.tryParse(r.first['deger'] as String);
  }
}
