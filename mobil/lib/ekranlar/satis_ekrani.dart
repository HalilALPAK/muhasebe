import 'package:flutter/material.dart';

import '../durum.dart';
import '../veri/veritabani.dart';
import '../yardimci.dart';
import 'ortak.dart';

/// Yeni satış veya mevcut fişi düzenleme. Kaydedince (müşteri kimliği, tarih) döner.
class SatisEkrani extends StatefulWidget {
  final String? musteriUuid, islemUuid;
  const SatisEkrani({super.key, this.musteriUuid, this.islemUuid});

  @override
  State<SatisEkrani> createState() => _SatisEkraniState();
}

class _SatisEkraniState extends State<SatisEkrani> {
  final _musteri = TextEditingController();
  final _fis = TextEditingController();
  final _tarih = TextEditingController(text: bugunGoster());
  final _urun = TextEditingController();
  final _adet = TextEditingController(text: '1');
  final _fiyat = TextEditingController();
  final _aciklama = TextEditingController();
  final _urunOdak = FocusNode();
  final List<Kalem> _kalemler = [];
  int? _duzenlenen;
  bool _yukleniyor = true;

  @override
  void initState() {
    super.initState();
    _yukle();
  }

  Future<void> _yukle() async {
    final id = widget.islemUuid;
    if (id != null) {
      final i = await vt.islem(id);
      if (i != null) {
        _musteri.text = i.musteriAd;
        _fis.text = '${i.fisNo}';
        _tarih.text = tarihGoster(i.tarih);
        _aciklama.text = i.aciklama;
        _kalemler.addAll(i.kalemler);
      }
    } else {
      _fis.text = '${await vt.sonrakiFisNo()}';
      final m = widget.musteriUuid;
      if (m != null) _musteri.text = (await vt.musteri(m))?.ad ?? '';
    }
    if (mounted) setState(() => _yukleniyor = false);
  }

  @override
  void dispose() {
    for (final c in [_musteri, _fis, _tarih, _urun, _adet, _fiyat, _aciklama]) {
      c.dispose();
    }
    _urunOdak.dispose();
    super.dispose();
  }

  Future<void> _urunSecildi(String urun) async {
    final f = await vt.sonFiyat(urun);
    if (f != null && _fiyat.text.trim().isEmpty) _fiyat.text = f.toStringAsFixed(2).replaceAll('.', ',');
  }

  void _kalemEkle() {
    final urun = _urun.text.trim();
    final adet = sayiOku(_adet.text), fiyat = sayiOku(_fiyat.text);
    if (urun.isEmpty || adet == null || adet <= 0 || fiyat == null || (fiyat < 0 && !kucuk(urun).contains('indirim'))) {
      mesajGoster(context, 'Ürün adı, pozitif adet ve fiyat girin.', hata: true);
      return;
    }
    setState(() {
      final d = _duzenlenen;
      if (d != null) {
        _kalemler[d] = Kalem(urun, adet, fiyat);
      } else {
        _kalemler.add(Kalem(urun, adet, fiyat));
      }
      _duzenlenen = null;
      _urun.clear();
      _adet.text = '1';
      _fiyat.clear();
    });
    _urunOdak.requestFocus();
  }

  void _kalemDuzenle(int i) {
    final k = _kalemler[i];
    setState(() {
      _duzenlenen = i;
      _urun.text = k.urun;
      _adet.text = adetYaz(k.adet);
      _fiyat.text = k.fiyat.toStringAsFixed(2).replaceAll('.', ',');
    });
  }

  Future<void> _kaydet() async {
    final ad = _musteri.text.trim();
    final tarih = tarihOku(_tarih.text);
    final fisNo = int.tryParse(_fis.text.trim());
    if (ad.isEmpty) return mesajGoster(context, 'Müşteri adını girin.', hata: true);
    if (_kalemler.isEmpty) return mesajGoster(context, 'En az bir ürün ekleyin.', hata: true);
    if (tarih == null) return mesajGoster(context, 'Tarihi GG.AA.YYYY biçiminde girin.', hata: true);
    if (fisNo == null || fisNo <= 0) return mesajGoster(context, 'Fiş numarası pozitif bir tam sayı olmalı.', hata: true);
    final kullanan = await vt.fisKullanan(fisNo, widget.islemUuid);
    if (kullanan != null) {
      final bos = await vt.sonrakiFisNo();
      if (mounted) mesajGoster(context, '$fisNo numaralı fiş zaten var ($kullanan). Boştaki ilk numara: $bos', hata: true);
      return;
    }
    final musteri = await vt.musteriBul(ad) ?? await vt.musteriKaydet(ad: ad);
    await vt.satisKaydet(uuid: widget.islemUuid, musteriUuid: musteri, tarih: tarih, kalemler: _kalemler, aciklama: _aciklama.text.trim(), fisNo: fisNo);
    if (mounted) Navigator.pop(context, (musteri, tarih));
  }

  @override
  Widget build(BuildContext context) {
    final toplam = _kalemler.fold<double>(0, (t, k) => t + k.tutar);
    return Scaffold(
      appBar: AppBar(title: Text(widget.islemUuid != null ? 'Fiş Düzenle' : 'Yeni Satış')),
      body: _yukleniyor
          ? const Center(child: CircularProgressIndicator())
          : Column(children: [
              Expanded(
                child: ListView(padding: const EdgeInsets.all(12), children: [
                  OneriAlani(denetleyici: _musteri, kaynak: vt.musteriAdlari, etiket: 'Müşteri', secildi: (_) => _urunOdak.requestFocus()),
                  const SizedBox(height: 10),
                  Row(children: [
                    Expanded(child: TextField(controller: _fis, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Fiş No'))),
                    const SizedBox(width: 10),
                    Expanded(
                      flex: 2,
                      child: TextField(
                        controller: _tarih,
                        keyboardType: TextInputType.number,
                        inputFormatters: [TarihBicimi()],
                        decoration: const InputDecoration(labelText: 'Tarih (GG.AA.YYYY)'),
                      ),
                    ),
                  ]),
                  const SizedBox(height: 12),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(10),
                      child: Column(children: [
                        OneriAlani(denetleyici: _urun, kaynak: vt.urunAdlari, etiket: 'Ürün Adı', odak: _urunOdak, secildi: _urunSecildi),
                        const SizedBox(height: 10),
                        Row(children: [
                          Expanded(child: TextField(controller: _adet, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: const InputDecoration(labelText: 'Adet'))),
                          const SizedBox(width: 10),
                          Expanded(
                            flex: 2,
                            child: TextField(
                              controller: _fiyat,
                              keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                              decoration: const InputDecoration(labelText: 'Birim Fiyat'),
                              onSubmitted: (_) => _kalemEkle(),
                            ),
                          ),
                          const SizedBox(width: 10),
                          FilledButton(onPressed: _kalemEkle, child: Text(_duzenlenen != null ? 'Güncelle' : 'Ekle')),
                        ]),
                      ]),
                    ),
                  ),
                  const SizedBox(height: 6),
                  for (var i = 0; i < _kalemler.length; i++)
                    Card(
                      child: ListTile(
                        dense: true,
                        title: Text(_kalemler[i].urun, style: const TextStyle(fontWeight: FontWeight.w600)),
                        subtitle: Text('${adetYaz(_kalemler[i].adet)} × ${para(_kalemler[i].fiyat)}'),
                        trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                          Text(para(_kalemler[i].tutar), style: const TextStyle(fontWeight: FontWeight.bold)),
                          IconButton(
                            icon: const Icon(Icons.delete_outline, color: kirmizi),
                            onPressed: () => setState(() {
                              _kalemler.removeAt(i);
                              _duzenlenen = null;
                            }),
                          ),
                        ]),
                        onTap: () => _kalemDuzenle(i),
                      ),
                    ),
                  const SizedBox(height: 8),
                  TextField(controller: _aciklama, decoration: const InputDecoration(labelText: 'Açıklama')),
                ]),
              ),
              Container(
                color: acikTuruncu,
                padding: const EdgeInsets.all(12),
                child: SafeArea(
                  top: false,
                  child: Row(children: [
                    Expanded(child: Text('Toplam: ${para(toplam)}', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold))),
                    FilledButton(key: const Key('satis_kaydet'), onPressed: _kaydet, child: const Text('KAYDET')),
                  ]),
                ),
              ),
            ]),
    );
  }
}
