import 'package:flutter/material.dart';

import '../durum.dart';
import '../yardimci.dart';
import 'cari_ekrani.dart';
import 'fis_ekrani.dart';
import 'sunucu_ekrani.dart';
import '../veri/bulut.dart';

class AnaEkran extends StatefulWidget {
  const AnaEkran({super.key});

  @override
  State<AnaEkran> createState() => _AnaEkranState();
}

class _AnaEkranState extends State<AnaEkran> {
  DateTime? _son;

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
    final s = await vt.sonEsitleme();
    if (mounted) setState(() => _son = s);
  }

  Future<void> _esitle() async {
    try {
      final s = await esitleyici.simdi();
      if (mounted) mesajGoster(context, 'Eşitlendi: ${s.gonderilen} kayıt gönderildi, ${s.alinan} kayıt alındı.');
    } on BulutHatasi catch (e) {
      if (mounted) mesajGoster(context, e.mesaj, hata: true);
    }
  }

  Widget _buyukDugme(String metin, String aciklama, Widget ekran) => Expanded(
        child: Column(children: [
          SizedBox(
            width: double.infinity,
            height: 96,
            child: FilledButton(
              key: Key('dugme_$metin'),
              style: FilledButton.styleFrom(shape: const RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(6)))),
              onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => ekran)),
              child: Text(metin, style: const TextStyle(fontSize: 30, fontWeight: FontWeight.bold)),
            ),
          ),
          const SizedBox(height: 6),
          Text(aciklama, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12, color: Color(0xFF8A7A6A))),
        ]),
      );

  @override
  Widget build(BuildContext context) {
    final son = _son;
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(children: [
              Image.asset('assets/logo.jpg', height: 190),
              const SizedBox(height: 10),
              const Text(firma, style: TextStyle(fontSize: 34, fontWeight: FontWeight.bold, color: turuncu)),
              const Text('Cari Hesap Takip', style: TextStyle(fontSize: 14, color: Color(0xFF8A7A6A))),
              const SizedBox(height: 34),
              Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                _buyukDugme('FİŞ', 'Satış fişi kes, tahsilat al', const FisEkrani()),
                const SizedBox(width: 16),
                _buyukDugme('CARİ', 'Müşteri hesapları, ekstre, WhatsApp', const CariEkrani()),
              ]),
              const SizedBox(height: 26),
              Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                OutlinedButton.icon(icon: const Icon(Icons.sync), label: const Text('Şimdi Eşitle'), onPressed: _esitle),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  icon: const Icon(Icons.cloud_outlined),
                  label: const Text('Sunucu'),
                  onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SunucuEkrani())),
                ),
              ]),
              const SizedBox(height: 6),
              ValueListenableBuilder<String>(
                valueListenable: esitleyici.durum,
                builder: (_, d, _) => Text(
                  d.isNotEmpty
                      ? '☁ $d'
                      : son == null
                          ? 'Henüz eşitlenmedi'
                          : 'Son eşitleme: ${bugunMu(son) ? 'bugün' : tarihGoster(tarihIso(son))} '
                              '${son.hour.toString().padLeft(2, '0')}:${son.minute.toString().padLeft(2, '0')}',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12, color: esitleyici.hata.value ? kirmizi : const Color(0xFF8A7A6A)),
                ),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

bool bugunMu(DateTime d) => tarihIso(d) == tarihIso(DateTime.now());
