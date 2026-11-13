import 'package:flutter/material.dart';

import 'durum.dart';
import 'ekranlar/ana_ekran.dart';
import 'veri/bulut.dart';
import 'veri/veritabani.dart';
import 'yardimci.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  vt = await Veritabani.ac();
  esitleyici = BulutEsitleyici(vt)..baslat();
  runApp(const OgulTarimUygulamasi());
}

class OgulTarimUygulamasi extends StatefulWidget {
  const OgulTarimUygulamasi({super.key});

  @override
  State<OgulTarimUygulamasi> createState() => _OgulTarimUygulamasiState();
}

class _OgulTarimUygulamasiState extends State<OgulTarimUygulamasi> with WidgetsBindingObserver {
  int _buYil = DateTime.now().year;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // uygulama açık kalırken yeni yıla girildiyse çalışma yılı da ilerler
    if (state != AppLifecycleState.resumed) return;
    esitleyici.tetikle();
    final yeni = DateTime.now().year;
    if (yeni != _buYil) {
      if (calismaYili.value == _buYil) calismaYili.value = yeni;
      _buYil = yeni;
    }
  }

  @override
  Widget build(BuildContext context) {
    final renkler = ColorScheme.fromSeed(seedColor: turuncu).copyWith(
      primary: turuncu,
      onPrimary: Colors.white,
      secondary: koyuTuruncu,
      surface: zemin,
    );
    return MaterialApp(
      title: 'Oğul Tarım',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: renkler,
        scaffoldBackgroundColor: zemin,
        appBarTheme: const AppBarTheme(backgroundColor: Colors.white, foregroundColor: turuncu, elevation: 1, centerTitle: false),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
          isDense: true,
          filled: true,
          fillColor: Colors.white,
        ),
        cardTheme: const CardThemeData(color: Colors.white, margin: EdgeInsets.symmetric(vertical: 3), elevation: 0.5),
      ),
      home: const AnaEkran(),
    );
  }
}
