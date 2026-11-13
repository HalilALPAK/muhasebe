import 'package:flutter/material.dart';

import '../durum.dart';
import '../veri/bulut.dart';
import '../yardimci.dart';

class SunucuEkrani extends StatefulWidget {
  const SunucuEkrani({super.key});

  @override
  State<SunucuEkrani> createState() => _SunucuEkraniState();
}

class _SunucuEkraniState extends State<SunucuEkrani> {
  final _url = TextEditingController();
  final _anahtar = TextEditingController();
  final _cihaz = TextEditingController();
  bool _gizli = true, _calisiyor = false;
  String? _sonuc;
  bool _basarili = false;
  String _eskiUrl = '';

  @override
  void initState() {
    super.initState();
    _yukle();
  }

  @override
  void dispose() {
    _url.dispose();
    _anahtar.dispose();
    _cihaz.dispose();
    super.dispose();
  }

  Future<void> _yukle() async {
    _eskiUrl = await vt.ayar('sunucu_url');
    _url.text = _eskiUrl.isEmpty ? varsayilanSunucu : _eskiUrl;
    _anahtar.text = await vt.ayar('sunucu_anahtar');
    _cihaz.text = await vt.ayar('cihaz', 'telefon');
    final b = await vt.bekleyenSayisi();
    if (mounted) setState(() => _sonuc = 'Bekleyen değişiklik: $b');
  }

  String get _adres {
    var u = _url.text.trim().replaceAll(RegExp(r'/+$'), '');
    if (u.isNotEmpty && !u.startsWith('http')) u = 'https://$u';
    return u;
  }

  Future<void> _test() async {
    setState(() => _calisiyor = true);
    try {
      final d = await durumSor(_adres, _anahtar.text.trim());
      _basarili = true;
      _sonuc = 'Bağlantı başarılı. Sunucuda ${d['musteri']} müşteri, ${d['islem']} işlem, ${d['gider']} gider var.';
    } on BulutHatasi catch (e) {
      _basarili = false;
      _sonuc = e.mesaj;
    }
    if (mounted) setState(() => _calisiyor = false);
  }

  Future<void> _kaydet() async {
    if (_adres != _eskiUrl) await vt.hepsiniGonderilecekYap(); // yeni sunucu: her şey baştan
    await vt.ayarYaz('sunucu_url', _adres);
    await vt.ayarYaz('sunucu_anahtar', _anahtar.text.trim());
    await vt.ayarYaz('cihaz', _cihaz.text.trim().isEmpty ? 'telefon' : _cihaz.text.trim());
    esitleyici.tetikle();
    if (mounted) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Sunucu Ayarları')),
        body: ListView(padding: const EdgeInsets.all(16), children: [
          const Text(
            'Laptop ve telefon aynı sunucu adresini ve anahtarı kullanınca kayıtlar internet üzerinden otomatik eşitlenir. '
            'İnternet yokken çalışmaya devam edersiniz; değişiklikler bağlantı gelince gönderilir.',
            style: TextStyle(color: Color(0xFF6A5A4A)),
          ),
          const SizedBox(height: 16),
          TextField(controller: _url, keyboardType: TextInputType.url, decoration: const InputDecoration(labelText: 'Sunucu adresi')),
          const SizedBox(height: 12),
          TextField(
            controller: _anahtar,
            obscureText: _gizli,
            decoration: InputDecoration(
              labelText: 'Sunucu anahtarı',
              suffixIcon: IconButton(icon: Icon(_gizli ? Icons.visibility : Icons.visibility_off), onPressed: () => setState(() => _gizli = !_gizli)),
            ),
          ),
          const SizedBox(height: 12),
          TextField(controller: _cihaz, decoration: const InputDecoration(labelText: 'Bu cihazın adı')),
          const SizedBox(height: 14),
          if (_sonuc != null) Text(_sonuc!, style: TextStyle(color: _basarili ? yesil : const Color(0xFF6A5A4A), fontWeight: FontWeight.w600)),
          const SizedBox(height: 14),
          Row(children: [
            Expanded(child: OutlinedButton(onPressed: _calisiyor ? null : _test, child: Text(_calisiyor ? 'Deneniyor…' : 'Bağlantıyı Test Et'))),
            const SizedBox(width: 10),
            Expanded(child: FilledButton(onPressed: _kaydet, child: const Text('Kaydet ve Eşitle'))),
          ]),
        ]),
      );
}
