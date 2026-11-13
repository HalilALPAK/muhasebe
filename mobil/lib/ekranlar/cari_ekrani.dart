import 'package:flutter/material.dart';

import '../durum.dart';
import '../veri/veritabani.dart';
import '../yardimci.dart';
import 'ortak.dart';

/// Tüm müşteriler ve bakiyeleri.
class CariEkrani extends StatefulWidget {
  const CariEkrani({super.key});

  @override
  State<CariEkrani> createState() => _CariEkraniState();
}

class _CariEkraniState extends State<CariEkrani> {
  String _ara = '';
  int? _yil;
  List<MusteriOzet> _liste = const [];

  @override
  void initState() {
    super.initState();
    vt.degisti.addListener(_yukle);
    _yukle();
  }

  @override
  void dispose() {
    vt.degisti.removeListener(_yukle);
    super.dispose();
  }

  Future<void> _yukle() async {
    final l = await vt.musteriler(ara: _ara, yil: _yil);
    if (mounted) setState(() => _liste = l);
  }

  @override
  Widget build(BuildContext context) {
    final toplam = _liste.fold<double>(0, (t, m) => t + m.bakiye);
    return Scaffold(
      appBar: AppBar(
        title: const Text('CARİ', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          YilSecici(
            deger: _yil,
            tumu: true,
            degisti: (y) {
              _yil = y;
              _yukle();
            },
          ),
          const SizedBox(width: 8),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        tooltip: 'Yeni Müşteri',
        onPressed: () async {
          final id = await musteriFormu(context);
          if (id != null && context.mounted) {
            Navigator.push(context, MaterialPageRoute(builder: (_) => MusteriDetayEkrani(musteriUuid: id, ilkYil: _yil)));
          }
        },
        child: const Icon(Icons.person_add_alt),
      ),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.all(10),
          child: TextField(
            decoration: const InputDecoration(labelText: 'Müşteri Ara', prefixIcon: Icon(Icons.search)),
            onChanged: (v) {
              _ara = v.trim();
              _yukle();
            },
          ),
        ),
        Expanded(
          child: ListView.separated(
            itemCount: _liste.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (_, i) {
              final m = _liste[i];
              return ListTile(
                dense: true,
                title: Text(m.ad, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                subtitle: m.telefon.isEmpty ? null : Text(m.telefon),
                trailing: Text(para(m.bakiye),
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: m.bakiye > 0.005 ? kirmizi : (m.bakiye < -0.005 ? yesil : null))),
                onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => MusteriDetayEkrani(musteriUuid: m.uuid, ilkYil: _yil))),
              );
            },
          ),
        ),
        Container(
          width: double.infinity,
          color: acikTuruncu,
          padding: const EdgeInsets.fromLTRB(14, 10, 14, 14),
          child: SafeArea(top: false, child: Text('Toplam alacak: ${para(toplam)}', key: const Key('toplam_alacak'), style: const TextStyle(fontWeight: FontWeight.bold))),
        ),
      ]),
    );
  }
}

/// Seçilen müşterinin bütün işlemleri.
class MusteriDetayEkrani extends StatefulWidget {
  final String musteriUuid;
  final int? ilkYil;
  const MusteriDetayEkrani({super.key, required this.musteriUuid, this.ilkYil});

  @override
  State<MusteriDetayEkrani> createState() => _MusteriDetayEkraniState();
}

class _MusteriDetayEkraniState extends State<MusteriDetayEkrani> {
  late int? _yil = widget.ilkYil;
  List<Islem> _islemler = const [];
  double _devir = 0;

  @override
  void initState() {
    super.initState();
    vt.degisti.addListener(_yukle);
    _yukle();
  }

  @override
  void dispose() {
    vt.degisti.removeListener(_yukle);
    super.dispose();
  }

  Future<void> _yukle() async {
    if (await vt.musteri(widget.musteriUuid) == null) {
      if (mounted) Navigator.pop(context); // silindi veya eşitlemede birleşti
      return;
    }
    final y = _yil;
    final d = y != null ? await vt.devir(widget.musteriUuid, y) : 0.0;
    final l = await vt.islemler(widget.musteriUuid, yil: y);
    if (mounted) {
      setState(() {
        _devir = d;
        _islemler = l;
      });
    }
  }

  Future<void> _musteriSil() async {
    final m = await vt.musteri(widget.musteriUuid);
    if (m == null || !mounted) return;
    if (await onayla(context, 'Müşteriyi Sil', "'${m.ad}' ve TÜM işlemleri silinecek. Emin misiniz?")) await vt.musteriSil(m.uuid);
  }

  @override
  Widget build(BuildContext context) {
    var bakiye = _devir;
    final y = _yil;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Hesap'),
        actions: [
          YilSecici(
            deger: y,
            tumu: true,
            degisti: (v) {
              _yil = v;
              _yukle();
            },
          ),
          PopupMenuButton<String>(
            onSelected: (s) => s == 'duzenle' ? musteriFormu(context, uuid: widget.musteriUuid) : _musteriSil(),
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'duzenle', child: Text('Müşteriyi Düzenle')),
              PopupMenuItem(value: 'sil', child: Text('Müşteriyi Sil')),
            ],
          ),
        ],
      ),
      body: ListView(padding: const EdgeInsets.all(10), children: [
        HesapKarti(musteriUuid: widget.musteriUuid, yil: y),
        const SizedBox(height: 10),
        if (y != null && _devir.abs() > 0.005)
          Card(
            color: acikTuruncu,
            child: ListTile(
              dense: true,
              title: Text('${y - 1} yılından devir', style: const TextStyle(fontWeight: FontWeight.bold)),
              subtitle: Text('01.01.$y'),
              trailing: Text(para(_devir), style: const TextStyle(fontWeight: FontWeight.bold)),
            ),
          ),
        for (final i in _islemler)
          Builder(builder: (_) {
            bakiye += i.satis ? i.tutar : -i.tutar;
            return IslemKarti(key: ValueKey(i.uuid), islem: i, musteriGoster: false, bakiye: bakiye);
          }),
        if (_islemler.isEmpty) const Padding(padding: EdgeInsets.all(24), child: Text('Bu dönemde işlem yok', textAlign: TextAlign.center)),
      ]),
    );
  }
}
