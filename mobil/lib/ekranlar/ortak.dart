import 'package:flutter/material.dart';

import '../durum.dart';
import '../veri/veritabani.dart';
import '../yardimci.dart';
import 'ekstre_ekrani.dart';
import 'satis_ekrani.dart';
import 'tahsilat_ekrani.dart';

/// Yazdıkça daha önce girilen kayıtlardan öneri gösteren giriş kutusu.
class OneriAlani extends StatefulWidget {
  final TextEditingController denetleyici;
  final Future<List<String>> Function() kaynak;
  final String etiket;
  final ValueChanged<String>? secildi;
  final ValueChanged<String>? gonderildi;
  final FocusNode? odak;

  const OneriAlani({super.key, required this.denetleyici, required this.kaynak, required this.etiket, this.secildi, this.gonderildi, this.odak});

  @override
  State<OneriAlani> createState() => _OneriAlaniState();
}

class _OneriAlaniState extends State<OneriAlani> {
  late final FocusNode _odak = widget.odak ?? FocusNode();
  List<String> _adaylar = const [];

  @override
  void initState() {
    super.initState();
    _odak.addListener(_yukle);
    _yukle();
  }

  @override
  void dispose() {
    _odak.removeListener(_yukle);
    if (widget.odak == null) _odak.dispose();
    super.dispose();
  }

  Future<void> _yukle() async {
    if (_odak.hasFocus || _adaylar.isEmpty) {
      final a = await widget.kaynak();
      if (mounted) _adaylar = a;
    }
  }

  Iterable<String> _eslesen(String metin) {
    final q = kucuk(metin.trim());
    if (q.isEmpty) return const [];
    final bas = _adaylar.where((a) => kucuk(a).startsWith(q)).toList();
    final ic = _adaylar.where((a) => kucuk(a).contains(q) && !bas.contains(a));
    final hepsi = {...bas, ...ic}.take(8).toList();
    return hepsi.length == 1 && kucuk(hepsi.first) == q ? const [] : hepsi;
  }

  @override
  Widget build(BuildContext context) => RawAutocomplete<String>(
        textEditingController: widget.denetleyici,
        focusNode: _odak,
        optionsBuilder: (v) => _eslesen(v.text),
        onSelected: widget.secildi,
        fieldViewBuilder: (_, c, f, gonder) => TextField(
          controller: c,
          focusNode: f,
          textInputAction: TextInputAction.next,
          decoration: InputDecoration(labelText: widget.etiket),
          onSubmitted: (v) {
            gonder();
            widget.gonderildi?.call(v);
          },
        ),
        optionsViewBuilder: (_, sec, secenekler) => Align(
          alignment: Alignment.topLeft,
          child: Material(
            elevation: 4,
            child: ConstrainedBox(
              constraints: BoxConstraints(maxHeight: 240, maxWidth: MediaQuery.sizeOf(context).width - 32),
              child: ListView(
                padding: EdgeInsets.zero,
                shrinkWrap: true,
                children: [
                  for (final s in secenekler) ListTile(dense: true, title: Text(s), onTap: () => sec(s)),
                ],
              ),
            ),
          ),
        ),
      );
}

/// Çalışma yılı / tüm yıllar seçimi. [tumu] true ise 'Tüm Yıllar' seçeneği eklenir (değer null).
class YilSecici extends StatefulWidget {
  final int? deger;
  final bool tumu;
  final ValueChanged<int?> degisti;
  const YilSecici({super.key, required this.deger, required this.degisti, this.tumu = false});

  @override
  State<YilSecici> createState() => _YilSeciciState();
}

class _YilSeciciState extends State<YilSecici> {
  List<int> _yillar = [DateTime.now().year];

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
    final y = await vt.yillar();
    if (mounted) setState(() => _yillar = y);
  }

  @override
  Widget build(BuildContext context) {
    final d = widget.deger;
    final liste = [..._yillar, if (d != null && !_yillar.contains(d)) d];
    return DropdownButton<int?>(
      value: d,
      underline: const SizedBox.shrink(),
      style: const TextStyle(color: koyuTuruncu, fontWeight: FontWeight.bold, fontSize: 15),
      items: [
        if (widget.tumu) const DropdownMenuItem<int?>(value: null, child: Text('Tüm Yıllar')),
        for (final y in liste) DropdownMenuItem<int?>(value: y, child: Text('$y')),
      ],
      onChanged: widget.degisti,
    );
  }
}

Future<String?> musteriFormu(BuildContext context, {String? uuid}) async {
  final m = uuid != null ? await vt.musteri(uuid) : null;
  if (!context.mounted) return null;
  final ad = TextEditingController(text: m?.ad);
  final tel = TextEditingController(text: m?.telefon);
  final not = TextEditingController(text: m?.notlar);
  return showDialog<String>(
    context: context,
    builder: (d) => AlertDialog(
      title: Text(uuid == null ? 'Yeni Müşteri' : 'Müşteri Düzenle'),
      content: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: ad, decoration: const InputDecoration(labelText: 'Ad Soyad / Firma *')),
          const SizedBox(height: 10),
          TextField(controller: tel, keyboardType: TextInputType.phone, decoration: const InputDecoration(labelText: 'Telefon')),
          const SizedBox(height: 10),
          TextField(controller: not, decoration: const InputDecoration(labelText: 'Not')),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(d), child: const Text('Vazgeç')),
        FilledButton(
          onPressed: () async {
            final a = ad.text.trim();
            if (a.isEmpty) return;
            final ayni = await vt.musteriBul(a);
            if (!d.mounted) return;
            if (ayni != null && ayni != uuid && !await onayla(d, 'Aynı isim', "'$a' adlı bir müşteri zaten var. Yine de kaydedilsin mi?")) return;
            final id = await vt.musteriKaydet(uuid: uuid, ad: a, telefon: tel.text.trim(), notlar: not.text.trim());
            if (d.mounted) Navigator.pop(d, id);
          },
          child: const Text('Kaydet'),
        ),
      ],
    ),
  );
}

/// Kaydedilen satışın yılı çalışma yılından farklıysa fişin görünmesi için o yıla geçer.
Future<(String, String)?> satisAc(BuildContext context, {String? musteriUuid, String? islemUuid}) async {
  final s = await Navigator.push<(String, String)>(
      context, MaterialPageRoute(builder: (_) => SatisEkrani(musteriUuid: musteriUuid, islemUuid: islemUuid)));
  if (s != null) calismaYili.value = int.parse(s.$2.substring(0, 4));
  return s;
}

Future<void> tahsilatAc(BuildContext context, String musteriUuid, {String? islemUuid}) =>
    Navigator.push(context, MaterialPageRoute(builder: (_) => TahsilatEkrani(musteriUuid: musteriUuid, islemUuid: islemUuid)));

void ekstreAc(BuildContext context, String musteriUuid, int? yil) => Navigator.push(
    context, MaterialPageRoute(builder: (_) => EkstreEkrani(musteriUuid: musteriUuid, yil: yil ?? DateTime.now().year)));

Future<void> islemDuzenle(BuildContext context, Islem i) async {
  if (i.satis) {
    await satisAc(context, musteriUuid: i.musteriUuid, islemUuid: i.uuid);
  } else {
    await tahsilatAc(context, i.musteriUuid, islemUuid: i.uuid);
  }
}

Future<void> islemSilSor(BuildContext context, Islem i) async {
  final ne = i.satis ? 'Fiş ${i.fisNo}' : 'Tahsilat';
  if (await onayla(context, 'İşlem Sil', '$ne (${i.musteriAd}) silinsin mi?')) await vt.islemSil(i.uuid);
}

/// Tek satırda fiş özeti; dokununca ürünler ve Düzenle/Sil açılır.
class IslemKarti extends StatelessWidget {
  final Islem islem;
  final bool vurgulu, musteriGoster;
  final double? bakiye;
  const IslemKarti({super.key, required this.islem, this.vurgulu = false, this.musteriGoster = true, this.bakiye});

  @override
  Widget build(BuildContext context) {
    final i = islem;
    final renk = i.satis ? const Color(0xFF3A2A1A) : yesil;
    final baslik = i.satis ? 'Fiş ${i.fisNo}' : 'Tahsilat';
    final alt = [tarihGoster(i.tarih), if (musteriGoster) i.musteriAd, if (i.aciklama.isNotEmpty) i.aciklama].join('  ·  ');
    return Card(
      color: vurgulu ? acikTuruncu : Colors.white,
      child: ExpansionTile(
        shape: const Border(),
        collapsedShape: const Border(),
        tilePadding: const EdgeInsets.symmetric(horizontal: 12),
        title: Text(baslik, style: TextStyle(fontWeight: vurgulu ? FontWeight.bold : FontWeight.w600, color: renk, fontSize: 15)),
        subtitle: Text(alt, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.5)),
        trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, mainAxisSize: MainAxisSize.min, children: [
          Text(para(i.tutar), style: TextStyle(fontWeight: FontWeight.bold, color: i.satis ? kirmizi : yesil)),
          if (bakiye != null) Text('Bakiye ${para(bakiye!)}', style: const TextStyle(fontSize: 11, color: Color(0xFF777777))),
        ]),
        children: [
          for (final k in i.kalemler)
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 2, 14, 2),
              child: Row(children: [
                Expanded(child: Text('• ${k.urun}', style: const TextStyle(fontSize: 13))),
                Text('${adetYaz(k.adet)} × ${para(k.fiyat)}', style: const TextStyle(fontSize: 12, color: Color(0xFF666666))),
                const SizedBox(width: 10),
                SizedBox(width: 92, child: Text(para(k.tutar), textAlign: TextAlign.end, style: const TextStyle(fontSize: 13))),
              ]),
            ),
          Row(mainAxisAlignment: MainAxisAlignment.end, children: [
            TextButton.icon(icon: const Icon(Icons.edit, size: 18), label: const Text('Düzenle'), onPressed: () => islemDuzenle(context, i)),
            TextButton.icon(
              icon: const Icon(Icons.delete_outline, size: 18, color: kirmizi),
              label: const Text('Sil', style: TextStyle(color: kirmizi)),
              onPressed: () => islemSilSor(context, i),
            ),
          ]),
        ],
      ),
    );
  }
}

class _Hesap {
  final Musteri musteri;
  final double devir, satis, tahsilat;
  const _Hesap(this.musteri, this.devir, this.satis, this.tahsilat);
  double get kalan => devir + satis - tahsilat;
}

/// Müşterinin borç özeti ve işlem düğmeleri (Fiş ve Cari ekranlarında aynı).
class HesapKarti extends StatefulWidget {
  final String musteriUuid;
  final int? yil;
  const HesapKarti({super.key, required this.musteriUuid, required this.yil});

  @override
  State<HesapKarti> createState() => _HesapKartiState();
}

class _HesapKartiState extends State<HesapKarti> {
  _Hesap? _h;

  @override
  void initState() {
    super.initState();
    vt.degisti.addListener(_yukle);
    _yukle();
  }

  @override
  void didUpdateWidget(HesapKarti e) {
    super.didUpdateWidget(e);
    if (e.musteriUuid != widget.musteriUuid || e.yil != widget.yil) _yukle();
  }

  @override
  void dispose() {
    vt.degisti.removeListener(_yukle);
    super.dispose();
  }

  Future<void> _yukle() async {
    final m = await vt.musteri(widget.musteriUuid);
    if (m == null) return;
    final y = widget.yil;
    final devir = y != null ? await vt.devir(m.uuid, y) : 0.0;
    double s = 0, t = 0;
    for (final i in await vt.islemler(m.uuid, yil: y)) {
      if (i.satis) {
        s += i.tutar;
      } else {
        t += i.tutar;
      }
    }
    if (mounted) setState(() => _h = _Hesap(m, devir, s, t));
  }

  Widget _kutu(String etiket, double deger, {Color? renk}) => Expanded(
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
          decoration: BoxDecoration(color: Colors.white, border: Border.all(color: const Color(0xFFE6D5C3)), borderRadius: BorderRadius.circular(6)),
          child: Column(children: [
            FittedBox(child: Text(etiket, style: const TextStyle(fontSize: 11, color: koyuTuruncu, fontWeight: FontWeight.bold))),
            const SizedBox(height: 2),
            FittedBox(child: Text(para(deger), style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: renk))),
          ]),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final h = _h;
    if (h == null) return const SizedBox(height: 120);
    final y = widget.yil;
    final kutular = <Widget>[
      if (y != null) _kutu('Devir', h.devir),
      _kutu(y != null ? '$y Satış' : 'Toplam Satış', h.satis),
      _kutu(y != null ? '$y Tahsilat' : 'Toplam Tahsilat', h.tahsilat),
      _kutu('Kalan Borç', h.kalan, renk: h.kalan > 0.005 ? kirmizi : yesil),
    ];
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(h.musteri.ad, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.bold, color: Color(0xFF3A2A1A))),
      if (h.musteri.telefon.isNotEmpty || h.musteri.notlar.isNotEmpty)
        Text([if (h.musteri.telefon.isNotEmpty) 'Tel: ${h.musteri.telefon}', if (h.musteri.notlar.isNotEmpty) h.musteri.notlar].join('   '),
            style: const TextStyle(fontSize: 13)),
      const SizedBox(height: 8),
      Row(children: [for (var i = 0; i < kutular.length; i++) ...[if (i > 0) const SizedBox(width: 5), kutular[i]]]),
      const SizedBox(height: 8),
      FilledButton.icon(
        icon: const Icon(Icons.share),
        label: const Text('WhatsApp / Ekstre Gönder'),
        onPressed: () => ekstreAc(context, h.musteri.uuid, y),
      ),
      Row(children: [
        Expanded(
          child: OutlinedButton(onPressed: () => satisAc(context, musteriUuid: h.musteri.uuid), child: const Text('+ Satış Yap')),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: OutlinedButton(onPressed: () => tahsilatAc(context, h.musteri.uuid), child: const Text('+ Tahsilat')),
        ),
      ]),
    ]);
  }
}
