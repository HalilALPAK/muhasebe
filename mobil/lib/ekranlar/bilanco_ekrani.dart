import 'dart:math';

import 'package:flutter/material.dart';

import '../durum.dart';
import '../veri/veritabani.dart';
import '../yardimci.dart';
import 'cari_ekrani.dart';
import 'ortak.dart';

/// Seçilen tarih aralığı için gelir/gider, satış ve müşteri istatistikleri.
class BilancoEkrani extends StatefulWidget {
  const BilancoEkrani({super.key});

  @override
  State<BilancoEkrani> createState() => _BilancoEkraniState();
}

class _BilancoEkraniState extends State<BilancoEkrani> {
  final _bas = TextEditingController();
  final _bit = TextEditingController();
  final _gTarih = TextEditingController(text: bugunGoster());
  final _gKategori = TextEditingController();
  final _gTutar = TextEditingController();
  final _gAciklama = TextEditingController();

  Map<String, double>? _o;
  List<(String, double, double, double)> _dokum = const [];
  bool _aylik = false;
  List<(String, double, int, double)> _urunler = const [];
  List<(String, String, double, double, double)> _musteriler = const [];
  List<Gider> _giderler = const [];

  @override
  void initState() {
    super.initState();
    vt.degisti.addListener(_yukle);
    _aralik('ay');
  }

  @override
  void dispose() {
    vt.degisti.removeListener(_yukle);
    for (final c in [_bas, _bit, _gTarih, _gKategori, _gTutar, _gAciklama]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _aralik(String kod) async {
    final b = DateTime.now();
    var bas = b, bit = b;
    switch (kod) {
      case 'hafta':
        bas = b.subtract(Duration(days: b.weekday - 1));
      case 'ay':
        bas = DateTime(b.year, b.month);
      case 'gecen':
        bit = DateTime(b.year, b.month, 0);
        bas = DateTime(bit.year, bit.month);
      case 'yil':
        bas = DateTime(calismaYili.value);
        bit = DateTime(calismaYili.value, 12, 31);
      case 'tumu':
        final ilk = await vt.ilkTarih();
        if (ilk != null) bas = DateTime.parse(ilk);
    }
    _bas.text = tarihGoster(tarihIso(bas));
    _bit.text = tarihGoster(tarihIso(bit));
    _yukle();
  }

  Future<void> _yukle() async {
    final bas = tarihOku(_bas.text), bit = tarihOku(_bit.text);
    if (bas == null || bit == null || bas.compareTo(bit) > 0) {
      if (mounted) mesajGoster(context, 'Tarih aralığını GG.AA.YYYY biçiminde doğru girin.', hata: true);
      return;
    }
    final aylik = DateTime.parse(bit).difference(DateTime.parse(bas)).inDays > 62;
    final o = await vt.ozet(bas, bit);
    final d = await vt.donemDokumu(bas, bit, aylik);
    final u = await vt.urunRaporu(bas, bit);
    final m = await vt.musteriRaporu(bas, bit);
    final g = await vt.giderler(bas, bit);
    if (mounted) {
      setState(() {
        _o = o;
        _dokum = d;
        _aylik = aylik;
        _urunler = u;
        _musteriler = m;
        _giderler = g;
      });
    }
  }

  Future<void> _giderEkle() async {
    final t = tarihOku(_gTarih.text), tutar = sayiOku(_gTutar.text);
    if (t == null || tutar == null || tutar <= 0) {
      mesajGoster(context, 'Tarih GG.AA.YYYY, tutar sıfırdan büyük sayı olmalı.', hata: true);
      return;
    }
    await vt.giderEkle(t, _gKategori.text.trim(), tutar, _gAciklama.text.trim());
    _gKategori.clear();
    _gTutar.clear();
    _gAciklama.clear();
  }

  Widget _kart(String etiket, String deger, {Color? renk}) => Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(color: Colors.white, border: Border.all(color: const Color(0xFFE6D5C3)), borderRadius: BorderRadius.circular(6)),
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          FittedBox(child: Text(etiket, style: const TextStyle(fontSize: 11.5, color: koyuTuruncu, fontWeight: FontWeight.bold))),
          const SizedBox(height: 3),
          FittedBox(child: Text(deger, style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: renk))),
        ]),
      );

  String _donem(String k) => _aylik ? '${k.substring(5, 7)}.${k.substring(0, 4)}' : tarihGoster(k);

  Widget _ozetSekmesi() {
    final o = _o;
    if (o == null) return const SizedBox.shrink();
    final net = o['tahsilat']! - o['gider']!, sonuc = o['ciro']! - o['gider']!;
    final n = o['satis_sayisi']!;
    return ListView(padding: const EdgeInsets.all(10), children: [
      GridView.count(
        crossAxisCount: 2,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        childAspectRatio: 2.5,
        mainAxisSpacing: 6,
        crossAxisSpacing: 6,
        children: [
          _kart('Toplam Satış (Ciro)', para(o['ciro']!)),
          _kart('Satış İşlemi Sayısı', '${n.toInt()}'),
          _kart('Tahsilat (Kasa Girişi)', para(o['tahsilat']!), renk: yesil),
          _kart('Gider (Kasa Çıkışı)', para(o['gider']!), renk: kirmizi),
          _kart('Net Kasa', para(net), renk: net >= 0 ? yesil : kirmizi),
          _kart('Dönem Sonucu', para(sonuc), renk: sonuc >= 0 ? yesil : kirmizi),
          _kart('Satılan Ürün Adedi', adetYaz(o['urun_adedi']!)),
          _kart('Ortalama Satış', n > 0 ? para(o['ciro']! / n) : '-'),
        ],
      ),
      const SizedBox(height: 6),
      _kart('Toplam Alacak (Bitiş Tarihinde)', para(o['alacak']!), renk: o['alacak']! > 0.005 ? kirmizi : null),
      const SizedBox(height: 10),
      SizedBox(height: 180, child: CustomPaint(painter: _Grafik(_dokum.map((d) => (_donem(d.$1), d.$2, d.$3, d.$4)).toList()))),
      const SizedBox(height: 8),
      for (final d in _dokum.reversed)
        Card(
          child: ListTile(
            dense: true,
            title: Text(_donem(d.$1), style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text('Satış ${para(d.$2)}  ·  Tahsilat ${para(d.$3)}  ·  Gider ${para(d.$4)}', style: const TextStyle(fontSize: 12)),
          ),
        ),
    ]);
  }

  Widget _urunSekmesi() {
    final ciro = _o?['ciro'] ?? 0;
    return ListView(padding: const EdgeInsets.all(10), children: [
      for (var i = 0; i < _urunler.length; i++)
        Card(
          child: ListTile(
            dense: true,
            leading: Text('${i + 1}', style: const TextStyle(fontWeight: FontWeight.bold, color: koyuTuruncu)),
            title: Text(_urunler[i].$1, style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text('${adetYaz(_urunler[i].$2)} adet  ·  ${_urunler[i].$3} satış  ·  ort. ${para(_urunler[i].$2 != 0 ? _urunler[i].$4 / _urunler[i].$2 : 0)}'),
            trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(para(_urunler[i].$4), style: const TextStyle(fontWeight: FontWeight.bold)),
              if (ciro > 0) Text('%${(_urunler[i].$4 / ciro * 100).toStringAsFixed(1).replaceAll('.', ',')}', style: const TextStyle(fontSize: 11)),
            ]),
          ),
        ),
    ]);
  }

  Widget _musteriSekmesi() => ListView(padding: const EdgeInsets.all(10), children: [
        for (final m in _musteriler)
          Card(
            child: ListTile(
              dense: true,
              title: Text(m.$2, style: const TextStyle(fontWeight: FontWeight.w600)),
              subtitle: Text('Satış ${para(m.$3)}  ·  Tahsilat ${para(m.$4)}'),
              trailing: Text(para(m.$5), style: TextStyle(fontWeight: FontWeight.bold, color: m.$5 > 0.005 ? kirmizi : null)),
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => MusteriDetayEkrani(musteriUuid: m.$1))),
            ),
          ),
      ]);

  Widget _giderSekmesi() {
    final kat = <String, double>{};
    for (final g in _giderler) {
      final k = g.kategori.isEmpty ? 'Diğer' : g.kategori;
      kat[k] = (kat[k] ?? 0) + g.tutar;
    }
    return ListView(padding: const EdgeInsets.all(10), children: [
      Card(
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(children: [
            Row(children: [
              Expanded(child: TextField(controller: _gTarih, keyboardType: TextInputType.number, inputFormatters: [TarihBicimi()], decoration: const InputDecoration(labelText: 'Tarih'))),
              const SizedBox(width: 8),
              Expanded(child: TextField(controller: _gTutar, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: const InputDecoration(labelText: 'Tutar'))),
            ]),
            const SizedBox(height: 8),
            OneriAlani(denetleyici: _gKategori, kaynak: vt.giderKategorileri, etiket: 'Kategori'),
            const SizedBox(height: 8),
            TextField(controller: _gAciklama, decoration: const InputDecoration(labelText: 'Açıklama')),
            const SizedBox(height: 8),
            SizedBox(width: double.infinity, child: FilledButton(onPressed: _giderEkle, child: const Text('Gider Ekle'))),
          ]),
        ),
      ),
      if (kat.isNotEmpty)
        Padding(
          padding: const EdgeInsets.all(6),
          child: Text((kat.entries.toList()..sort((a, b) => b.value.compareTo(a.value))).map((e) => '${e.key}: ${para(e.value)}').join('   |   '), style: const TextStyle(fontSize: 12)),
        ),
      for (final g in _giderler.reversed)
        Card(
          child: ListTile(
            dense: true,
            title: Text(g.kategori.isEmpty ? 'Diğer' : g.kategori, style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text([tarihGoster(g.tarih), if (g.aciklama.isNotEmpty) g.aciklama].join('  ·  ')),
            trailing: Row(mainAxisSize: MainAxisSize.min, children: [
              Text(para(g.tutar), style: const TextStyle(fontWeight: FontWeight.bold, color: kirmizi)),
              IconButton(
                icon: const Icon(Icons.delete_outline, color: kirmizi),
                onPressed: () async {
                  if (await onayla(context, 'Gider Sil', 'Seçili gider silinsin mi?')) await vt.giderSil(g.uuid);
                },
              ),
            ]),
          ),
        ),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    TextField tarihKutusu(TextEditingController c, String e) => TextField(
        controller: c, keyboardType: TextInputType.number, inputFormatters: [TarihBicimi()], decoration: InputDecoration(labelText: e), onSubmitted: (_) => _yukle());
    return DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Bilanço / Raporlar'),
          bottom: const TabBar(isScrollable: true, tabs: [Tab(text: 'Özet'), Tab(text: 'Ürünler'), Tab(text: 'Müşteriler'), Tab(text: 'Giderler')]),
        ),
        body: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 10, 10, 2),
            child: Row(children: [
              Expanded(child: tarihKutusu(_bas, 'Başlangıç')),
              const SizedBox(width: 8),
              Expanded(child: tarihKutusu(_bit, 'Bitiş')),
              IconButton(tooltip: 'Göster', icon: const Icon(Icons.refresh, color: turuncu), onPressed: _yukle),
            ]),
          ),
          SizedBox(
            height: 44,
            child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 8), children: [
              for (final (ad, kod) in const [('Bugün', 'gun'), ('Bu Hafta', 'hafta'), ('Bu Ay', 'ay'), ('Geçen Ay', 'gecen'), ('Çalışma Yılı', 'yil'), ('Tümü', 'tumu')])
                Padding(padding: const EdgeInsets.symmetric(horizontal: 3), child: ActionChip(label: Text(ad), onPressed: () => _aralik(kod))),
            ]),
          ),
          Expanded(child: TabBarView(children: [_ozetSekmesi(), _urunSekmesi(), _musteriSekmesi(), _giderSekmesi()])),
        ]),
      ),
    );
  }
}

class _Grafik extends CustomPainter {
  final List<(String, double, double, double)> veri;
  _Grafik(this.veri);

  static const _renkler = [turuncu, yesil, kirmizi];

  void _yaz(Canvas c, String m, Offset o, {double boyut = 9, Color renk = const Color(0xFF555555)}) {
    (TextPainter(text: TextSpan(text: m, style: TextStyle(fontSize: boyut, color: renk)), textDirection: TextDirection.ltr)..layout()).paint(c, o);
  }

  @override
  void paint(Canvas c, Size s) {
    if (veri.isEmpty) {
      _yaz(c, 'Bu aralıkta kayıt yok', Offset(s.width / 2 - 50, s.height / 2), boyut: 13);
      return;
    }
    const alt = 18.0, ust = 20.0;
    final en = veri.map((v) => max(v.$2, max(v.$3, v.$4))).reduce(max);
    final enBuyuk = en > 0 ? en : 1;
    final h = s.height - alt - ust;
    final grup = s.width / veri.length;
    final cubuk = min(grup * 0.8 / 3, 18.0);
    final adim = max(1, (veri.length * 54 / s.width).ceil());
    for (var j = 0; j < veri.length; j++) {
      final x0 = j * grup + (grup - 3 * cubuk) / 2;
      final d = [veri[j].$2, veri[j].$3, veri[j].$4];
      for (var k = 0; k < 3; k++) {
        if (d[k] > 0) {
          c.drawRect(Rect.fromLTRB(x0 + k * cubuk, s.height - alt - h * d[k] / enBuyuk, x0 + (k + 1) * cubuk - 1, s.height - alt), Paint()..color = _renkler[k]);
        }
      }
      if (j % adim == 0) _yaz(c, veri[j].$1.length > 7 ? veri[j].$1.substring(0, 5) : veri[j].$1, Offset(j * grup + 2, s.height - alt + 3));
    }
    var x = 0.0;
    for (var k = 0; k < 3; k++) {
      c.drawRect(Rect.fromLTWH(x, 3, 10, 10), Paint()..color = _renkler[k]);
      _yaz(c, const ['Satış', 'Tahsilat', 'Gider'][k], Offset(x + 13, 1), boyut: 11);
      x += 72;
    }
  }

  @override
  bool shouldRepaint(_Grafik e) => e.veri != veri;
}
