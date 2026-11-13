import 'package:flutter/material.dart';

import '../durum.dart';
import '../yardimci.dart';

class TahsilatEkrani extends StatefulWidget {
  final String musteriUuid;
  final String? islemUuid;
  const TahsilatEkrani({super.key, required this.musteriUuid, this.islemUuid});

  @override
  State<TahsilatEkrani> createState() => _TahsilatEkraniState();
}

class _TahsilatEkraniState extends State<TahsilatEkrani> {
  final _tarih = TextEditingController(text: bugunGoster());
  final _tutar = TextEditingController();
  final _aciklama = TextEditingController();
  String _ad = '';

  @override
  void initState() {
    super.initState();
    _yukle();
  }

  @override
  void dispose() {
    _tarih.dispose();
    _tutar.dispose();
    _aciklama.dispose();
    super.dispose();
  }

  Future<void> _yukle() async {
    final m = await vt.musteri(widget.musteriUuid);
    final id = widget.islemUuid;
    final i = id != null ? await vt.islem(id) : null;
    if (!mounted) return;
    setState(() {
      _ad = m?.ad ?? '';
      if (i != null) {
        _tarih.text = tarihGoster(i.tarih);
        _tutar.text = i.tutar.toStringAsFixed(2).replaceAll('.', ',');
        _aciklama.text = i.aciklama;
      }
    });
  }

  Future<void> _kaydet() async {
    final tarih = tarihOku(_tarih.text);
    final tutar = sayiOku(_tutar.text);
    if (tarih == null || tutar == null || tutar <= 0) {
      mesajGoster(context, 'Tarih GG.AA.YYYY, tutar sıfırdan büyük sayı olmalı.', hata: true);
      return;
    }
    await vt.tahsilatKaydet(uuid: widget.islemUuid, musteriUuid: widget.musteriUuid, tarih: tarih, tutar: tutar, aciklama: _aciklama.text.trim());
    if (mounted) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(widget.islemUuid != null ? 'Tahsilat Düzenle' : 'Tahsilat (Ödeme Al)')),
        body: ListView(padding: const EdgeInsets.all(14), children: [
          Text(_ad, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 14),
          TextField(
            controller: _tarih,
            keyboardType: TextInputType.number,
            inputFormatters: [TarihBicimi()],
            decoration: const InputDecoration(labelText: 'Tarih (GG.AA.YYYY)'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _tutar,
            autofocus: true,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'Tutar'),
          ),
          const SizedBox(height: 12),
          TextField(controller: _aciklama, decoration: const InputDecoration(labelText: 'Açıklama')),
          const SizedBox(height: 20),
          FilledButton(onPressed: _kaydet, child: const Text('KAYDET')),
        ]),
      );
}
