import 'package:flutter/foundation.dart';

import 'veri/bulut.dart';
import 'veri/veritabani.dart';

/// Uygulama boyunca kullanılan veritabanı.
late Veritabani vt;

/// Arka planda sunucuyla eşitleyen nesne.
late BulutEsitleyici esitleyici;

/// Fiş ekranındaki çalışma yılı.
final calismaYili = ValueNotifier<int>(DateTime.now().year);
