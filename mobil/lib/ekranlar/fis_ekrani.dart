import 'package:flutter/material.dart';

import '../durum.dart';
import '../veri/veritabani.dart';
import '../yardimci.dart';
import 'bilanco_ekrani.dart';
import 'ortak.dart';

/// Satış ekranı: sadece adı yazılıp seçilen müşterinin hesabı görünür, altta son girilen işlemler.
class FisEkrani extends StatefulWidget {
  const FisEkrani({super.key});

  @override
  State<FisEkrani> createState() => _FisEkraniState();
}

class _FisEkraniState extends State<FisEkrani> {
  final _ara = TextEditingController();
  String? _secili;
  bool _sadeceSecili = false;
  List<Islem> _son = const [];

  @override
  void initState() {
    super.initState();
    vt.degisti.addListener(_yukle);
    _yukle();
  }

  @override
  void dispose() {
    vt.degisti.removeListener(_yukle);
    _ara.dispose();
    super.dispose();
  }

  Future<void> _yukle() async {
    var secili = _secili;
    if (secili != null && await vt.musteri(secili) == null) secili = null; // silindi veya birleşti
    final s = await vt.sonIslemler(musteriUuid: _sadeceSecili ? secili : null);
    if (mounted) {
      setState(() {
        _secili = secili;
        _son = s;
      });
    }
  }

  Future<void> _musteriSec(String ad) async {
    final m = await vt.musteriBul(ad);
    if (m != null) {
      _secili = m;
      _yukle();
    } else if (mounted) {
      mesajGoster(context, "'$ad' adlı müşteri kayıtlı değil. Yeni Satış ile bu adı yazarsanız otomatik eklenir.");
    }
  }

  void _temizle() {
    _ara.clear();
    _secili = null;
    _yukle();
  }

  Future<void> _yeniSatis() async {
    final s = await satisAc(context, musteriUuid: _secili);
    if (s != null) {
      _secili = s.$1;
      _ara.text = (await vt.musteri(s.$1))?.ad ?? ''; // arama kutusu gösterilen müşteriyle aynı olsun
      _yukle();
    }
  }

  Future<void> _yeniMusteri() async {
    final id = await musteriFormu(context);
    if (id == null) return;
    final m = await vt.musteri(id);
    _ara.text = m?.ad ?? '';
    _secili = id;
    _yukle();
  }

  @override
  Widget build(BuildContext context) {
    final secili = _secili;
    return ValueListenableBuilder<int>(
      valueListenable: calismaYili,
      builder: (context, yil, _) => Scaffold(
        appBar: AppBar(
          title: const Text('FİŞ', style: TextStyle(fontWeight: FontWeight.bold)),
          actions: [
            YilSecici(deger: yil, degisti: (y) => calismaYili.value = y ?? yil),
            IconButton(
              tooltip: 'Bilanço / Raporlar',
              icon: const Icon(Icons.bar_chart),
              onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const BilancoEkrani())),
            ),
            IconButton(tooltip: 'Yeni Müşteri', icon: const Icon(Icons.person_add_alt), onPressed: _yeniMusteri),
          ],
        ),
        floatingActionButton: FloatingActionButton.extended(
          key: const Key('yeni_satis'),
          onPressed: _yeniSatis,
          icon: const Icon(Icons.add),
          label: const Text('Yeni Satış'),
        ),
        body: ListView(
          padding: const EdgeInsets.fromLTRB(10, 10, 10, 90),
          children: [
            Row(children: [
              Expanded(
                child: OneriAlani(denetleyici: _ara, kaynak: vt.musteriAdlari, etiket: 'Müşteri', secildi: _musteriSec, gonderildi: _musteriSec),
              ),
              IconButton(tooltip: 'Temizle', icon: const Icon(Icons.clear), onPressed: _temizle),
            ]),
            if (secili != null) ...[
              const SizedBox(height: 8),
              HesapKarti(musteriUuid: secili, yil: yil),
            ],
            const SizedBox(height: 12),
            Row(children: [
              const Expanded(child: Text('Son Girilen İşlemler', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF3A2A1A)))),
              if (secili != null) ...[
                const Text('Sadece seçili', style: TextStyle(fontSize: 12)),
                Switch(
                  value: _sadeceSecili,
                  onChanged: (d) {
                    _sadeceSecili = d;
                    _yukle();
                  },
                ),
              ],
            ]),
            if (_son.isEmpty) const Padding(padding: EdgeInsets.all(24), child: Text('Henüz işlem girilmedi', textAlign: TextAlign.center)),
            for (var i = 0; i < _son.length; i++) IslemKarti(key: ValueKey(_son[i].uuid), islem: _son[i], vurgulu: i == 0),
          ],
        ),
      ),
    );
  }
}
