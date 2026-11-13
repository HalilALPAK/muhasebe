import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../ekstre/ekstre_pdf.dart';
import '../yardimci.dart';

/// Logolu ekstreyi görsel ve PDF olarak hazırlar; paylaşım menüsünden WhatsApp'a gönderilir.
class EkstreEkrani extends StatefulWidget {
  final String musteriUuid;
  final int yil;
  const EkstreEkrani({super.key, required this.musteriUuid, required this.yil});

  @override
  State<EkstreEkrani> createState() => _EkstreEkraniState();
}

class _EkstreEkraniState extends State<EkstreEkrani> {
  bool _sadeceYil = false;
  EkstreVeri? _v;
  List<File> _pngler = const [];
  List<Uint8List> _gorseller = const [];
  File? _pdf;
  String? _hata;

  @override
  void initState() {
    super.initState();
    _olustur();
  }

  Future<void> _olustur() async {
    setState(() {
      _pdf = null;
      _hata = null;
    });
    try {
      final v = await ekstreVerisi(widget.musteriUuid, _sadeceYil ? widget.yil : null);
      final pdf = await ekstrePdf(v);
      final gorseller = await ekstrePng(pdf);
      final klasor = await getTemporaryDirectory();
      final ad = v.ad.replaceAll(RegExp(r'[\\/:*?"<>|]'), '').trim().replaceAll(' ', '_');
      final taban = p.join(klasor.path, 'Ekstre_${ad}_${tarihIso(DateTime.now())}');
      final pdfDosya = await File('$taban.pdf').writeAsBytes(pdf);
      final pngler = <File>[];
      for (var i = 0; i < gorseller.length; i++) {
        pngler.add(await File('$taban${gorseller.length > 1 ? '_s${i + 1}' : ''}.png').writeAsBytes(gorseller[i]));
      }
      if (mounted) {
        setState(() {
          _v = v;
          _pdf = pdfDosya;
          _pngler = pngler;
          _gorseller = gorseller;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _hata = 'Ekstre oluşturulamadı: $e');
    }
  }

  String _mesaj(EkstreVeri v) {
    final etiket = v.bakiye < -0.005
        ? 'Alacak bakiyeniz'
        : (v.yil != null && v.yil! < DateTime.now().year ? '${v.yil} yılı sonu borç bakiyeniz' : 'Güncel borç bakiyeniz');
    return 'Sayın ${v.ad},\n$firma hesap ekstreniz ektedir.\n$etiket: ${para(v.bakiye.abs())}\nİyi günler dileriz.';
  }

  Future<void> _paylas(List<File> dosyalar) async {
    final v = _v;
    if (v == null) return;
    await SharePlus.instance.share(ShareParams(files: [for (final d in dosyalar) XFile(d.path)], text: _mesaj(v)));
  }

  @override
  Widget build(BuildContext context) {
    final pdf = _pdf;
    final h = _hata;
    return Scaffold(
      appBar: AppBar(title: const Text('Ekstre Gönder')),
      body: h != null
          ? Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(h)))
          : Column(children: [
              Padding(
                padding: const EdgeInsets.all(10),
                child: SegmentedButton<bool>(
                  segments: [
                    const ButtonSegment(value: false, label: Text('Tüm işlemler')),
                    ButtonSegment(value: true, label: Text('Sadece ${widget.yil}')),
                  ],
                  selected: {_sadeceYil},
                  onSelectionChanged: (s) {
                    _sadeceYil = s.first;
                    _olustur();
                  },
                ),
              ),
              Expanded(
                child: pdf == null
                    ? const Center(child: CircularProgressIndicator())
                    : InteractiveViewer(
                        maxScale: 5,
                        child: ListView(padding: const EdgeInsets.symmetric(horizontal: 10), children: [
                          for (final g in _gorseller) Padding(padding: const EdgeInsets.only(bottom: 8), child: Image.memory(g)),
                        ]),
                      ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(10, 6, 10, 2),
                child: SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    icon: const Icon(Icons.share),
                    label: const Text('Görsel + PDF Paylaş (WhatsApp)'),
                    onPressed: pdf == null ? null : () => _paylas([..._pngler, pdf]),
                  ),
                ),
              ),
              SafeArea(
                top: false,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(10, 0, 10, 8),
                  child: Row(children: [
                    Expanded(child: OutlinedButton(onPressed: pdf == null ? null : () => _paylas(_pngler), child: const Text('Sadece Görsel'))),
                    const SizedBox(width: 8),
                    Expanded(child: OutlinedButton(onPressed: pdf == null ? null : () => _paylas([pdf]), child: const Text('Sadece PDF'))),
                  ]),
                ),
              ),
            ]),
    );
  }
}
