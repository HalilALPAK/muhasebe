"""Muhasebe verilerini Excel'e aktarma ve Excel'den satış / tahsilat okuma."""
from datetime import datetime, date, timedelta

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from muhasebe import kucuk, sayi_oku

PARA = '#,##0.00 "₺"'
TARIH = "DD.MM.YYYY"
BASLIK_FONT = Font(bold=True, color="FFFFFF")
BASLIK_DOLGU = PatternFill("solid", fgColor="F17E01")

# Excel'deki başlıkların hangi alana karşılık geldiği (küçük harfle)
ALANLAR = {
    "tarih": ["tarih", "işlem tarihi", "satış tarihi", "ödeme tarihi"],
    "musteri": ["müşteri", "müşteri adı", "müşteri adı soyadı", "cari", "cari adı",
                "ad soyad", "adı soyadı", "firma", "kişi"],
    "urun": ["ürün", "ürün adı", "ürün / hizmet", "mal", "malzeme", "stok adı"],
    "adet": ["adet", "miktar"],
    "fiyat": ["birim fiyat", "birim fiyatı", "fiyat", "fiyatı"],
    "tutar": ["tutar", "toplam", "toplam tutar"],
    "aciklama": ["açıklama", "not"],
    "fis": ["fiş no", "fiş", "satış no", "fatura no", "belge no"],
}


# ---------------------------------------------------------------- dışa aktarma
def _sayfa(wb, ad, basliklar, satirlar, para_kolonlari=(), tarih_kolonlari=(), genislikler=None):
    ws = wb.create_sheet(ad)
    ws.append(basliklar)
    for h in ws[1]:
        h.font, h.fill = BASLIK_FONT, BASLIK_DOLGU
        h.alignment = Alignment(horizontal="center")
    for s in satirlar:
        ws.append(list(s))
    for c in para_kolonlari:
        for (h,) in ws.iter_rows(min_row=2, min_col=c, max_col=c):
            h.number_format = PARA
    for c in tarih_kolonlari:
        for (h,) in ws.iter_rows(min_row=2, min_col=c, max_col=c):
            h.number_format = TARIH
    for i, g in enumerate(genislikler or [], 1):
        ws.column_dimensions[get_column_letter(i)].width = g
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def _d(iso):
    return date.fromisoformat(iso)


def disa_aktar(db, yol):
    """Müşteriler, satışlar, tahsilatlar ve giderleri tek bir Excel dosyasına yazar."""
    wb = Workbook()
    wb.remove(wb.active)

    musteriler = db.sorgu("""
        SELECT m.ad, m.telefon, m.notlar,
               COALESCE(SUM(CASE WHEN i.tur='SATIŞ' THEN i.tutar END), 0),
               COALESCE(SUM(CASE WHEN i.tur='TAHSİLAT' THEN i.tutar END), 0)
        FROM musteri m LEFT JOIN islem i ON i.musteri_id = m.id
        GROUP BY m.id ORDER BY m.ad COLLATE NOCASE""")
    ws = _sayfa(wb, "Müşteriler",
                ["Müşteri", "Telefon", "Not", "Toplam Satış", "Toplam Tahsilat", "Kalan Borç"],
                [(ad, tel, nt, s, t, s - t) for ad, tel, nt, s, t in musteriler],
                para_kolonlari=(4, 5, 6), genislikler=[32, 16, 30, 16, 16, 16])
    son = ws.max_row
    ws.append(["TOPLAM", None, None] + [f"=SUM({c}2:{c}{son})" for c in "DEF"])
    for h in ws[ws.max_row]:
        h.font = Font(bold=True)
        h.number_format = PARA

    _sayfa(wb, "Satışlar",
           ["Fiş No", "Tarih", "Müşteri", "Ürün", "Adet", "Birim Fiyat", "Tutar", "Açıklama"],
           [(fis, _d(t), m, u, a, f, round(a * f, 2), ac) for fis, t, m, u, a, f, ac in db.sorgu("""
               SELECT i.fis_no, i.tarih, m.ad, k.urun, k.adet, k.birim_fiyat, i.aciklama
               FROM kalem k JOIN islem i ON i.id = k.islem_id JOIN musteri m ON m.id = i.musteri_id
               ORDER BY i.tarih, i.id, k.id""")],
           para_kolonlari=(6, 7), tarih_kolonlari=(2,), genislikler=[8, 12, 30, 30, 8, 14, 14, 30])

    _sayfa(wb, "Tahsilatlar", ["Tarih", "Müşteri", "Tutar", "Açıklama"],
           [(_d(t), m, tu, ac) for t, m, tu, ac in db.sorgu("""
               SELECT i.tarih, m.ad, i.tutar, i.aciklama FROM islem i
               JOIN musteri m ON m.id = i.musteri_id
               WHERE i.tur='TAHSİLAT' ORDER BY i.tarih, i.id""")],
           para_kolonlari=(3,), tarih_kolonlari=(1,), genislikler=[12, 30, 14, 30])

    _sayfa(wb, "Giderler", ["Tarih", "Kategori", "Tutar", "Açıklama"],
           [(_d(t), k, tu, ac) for t, k, tu, ac in db.sorgu(
               "SELECT tarih, kategori, tutar, aciklama FROM gider ORDER BY tarih, id")],
           para_kolonlari=(3,), tarih_kolonlari=(1,), genislikler=[12, 20, 14, 40])
    wb.save(yol)


def sablon_olustur(yol):
    """Eski satışları girmek için boş örnek dosya."""
    wb = Workbook()
    wb.remove(wb.active)
    bugun = date.today()
    _sayfa(wb, "Satışlar", ["Fiş No", "Tarih", "Müşteri", "Ürün", "Adet", "Birim Fiyat", "Açıklama"],
           [(1, bugun, "Örnek Müşteri", "Örnek Ürün A", 2, 150, ""),
            (1, bugun, "Örnek Müşteri", "Örnek Ürün B", 1, 75.5, "")],
           para_kolonlari=(6,), tarih_kolonlari=(2,), genislikler=[8, 12, 30, 30, 8, 14, 30])
    _sayfa(wb, "Tahsilatlar", ["Tarih", "Müşteri", "Tutar", "Açıklama"],
           [(bugun, "Örnek Müşteri", 100, "Nakit")],
           para_kolonlari=(3,), tarih_kolonlari=(1,), genislikler=[12, 30, 14, 30])
    ws = wb.create_sheet("Açıklama")
    for satir in [
        "Örnek satırları silip kendi kayıtlarınızı yazın.",
        "Satışlar sayfası: Tarih, Müşteri, Ürün, Adet ve Birim Fiyat zorunludur "
        "(Birim Fiyat yerine Tutar sütunu da kullanılabilir).",
        "Aynı Fiş No'ya sahip satırlar tek satış olarak kaydedilir. Fiş No yoksa aynı müşterinin "
        "aynı tarihteki satırları tek satış sayılır.",
        "Tahsilatlar sayfası (isteğe bağlı): Tarih, Müşteri, Tutar.",
        "Programda olmayan müşteriler otomatik olarak oluşturulur.",
    ]:
        ws.append([satir])
    ws.column_dimensions["A"].width = 110
    wb.save(yol)


# ---------------------------------------------------------------- içe aktarma
def _tarih(v):
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, (int, float)):           # Excel seri tarih numarası
        return (date(1899, 12, 30) + timedelta(days=int(v))).isoformat()
    metin = str(v or "").strip().split(" ")[0]
    for bicim in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(metin, bicim).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"tarih anlaşılamadı: {v!r}")


def _sayi(v):
    if isinstance(v, (int, float)):
        return float(v)
    return sayi_oku(str(v or ""))


def _baslik_bul(ws):
    """İlk 10 satırda başlık satırını arar: (satır no, {alan: sütun indeksi})."""
    for r, satir in enumerate(ws.iter_rows(min_row=1, max_row=10, values_only=True), 1):
        kolonlar = {}
        for c, deger in enumerate(satir):
            ad = " ".join(kucuk(str(deger or "")).replace("₺", "").replace("(", " ")
                          .replace(")", " ").replace(":", " ").split())
            for alan, adlar in ALANLAR.items():
                if ad in adlar and alan not in kolonlar:
                    kolonlar[alan] = c
        if "tarih" in kolonlar and "musteri" in kolonlar:
            return r, kolonlar
    return None, None


def oku(yol):
    """Excel'den satışları ve tahsilatları okur.

    Dönüş: (satislar, tahsilatlar, uyarilar)
      satislar: [{"musteri", "tarih", "aciklama", "kalemler": [(ürün, adet, fiyat), ...]}, ...]
      tahsilatlar: [{"musteri", "tarih", "tutar", "aciklama"}, ...]
    """
    wb = load_workbook(yol, data_only=True, read_only=True)
    satislar, tahsilatlar, uyarilar = {}, [], []
    for ws in wb.worksheets:
        bas, k = _baslik_bul(ws)
        if bas is None:
            continue
        satis_sayfasi = "urun" in k
        if not satis_sayfasi and not ("tutar" in k and "tahsilat" in kucuk(ws.title)):
            continue

        def al(satir, alan):
            i = k.get(alan)
            return satir[i] if i is not None and i < len(satir) else None

        for r, satir in enumerate(ws.iter_rows(min_row=bas + 1, values_only=True), bas + 1):
            if not any(v not in (None, "") for v in satir):
                continue
            musteri = str(al(satir, "musteri") or "").strip()
            if kucuk(musteri) in ("toplam", "genel toplam"):
                continue
            try:
                if not musteri:
                    raise ValueError("müşteri adı boş")
                tarih = _tarih(al(satir, "tarih"))
                aciklama = str(al(satir, "aciklama") or "").strip()
                if satis_sayfasi:
                    urun = str(al(satir, "urun") or "").strip()
                    if not urun:
                        raise ValueError("ürün adı boş")
                    adet = _sayi(al(satir, "adet")) if al(satir, "adet") not in (None, "") else 1.0
                    if adet <= 0:
                        raise ValueError("adet sıfırdan büyük olmalı")
                    if al(satir, "fiyat") not in (None, ""):
                        fiyat = _sayi(al(satir, "fiyat"))
                    elif al(satir, "tutar") not in (None, ""):
                        fiyat = round(_sayi(al(satir, "tutar")) / adet, 4)
                    else:
                        raise ValueError("birim fiyat / tutar boş")
                    fis = al(satir, "fis")
                    fis = str(fis).strip() if fis not in (None, "") else ""
                    anahtar = (ws.title, fis, kucuk(musteri), tarih)
                    s = satislar.setdefault(anahtar, {"musteri": musteri, "tarih": tarih, "fis": fis,
                                                      "aciklama": aciklama, "kalemler": []})
                    s["kalemler"].append((urun, adet, fiyat))
                else:
                    tutar = _sayi(al(satir, "tutar"))
                    if tutar <= 0:
                        raise ValueError("tutar sıfırdan büyük olmalı")
                    tahsilatlar.append({"musteri": musteri, "tarih": tarih,
                                        "tutar": tutar, "aciklama": aciklama})
            except ValueError as e:
                uyarilar.append(f"'{ws.title}' sayfası, satır {r}: {e or 'sayı anlaşılamadı'} (atlandı)")
    wb.close()
    return list(satislar.values()), tahsilatlar, uyarilar


def zaten_var(db, kayit, satis):
    """Aynı müşteri, tarih ve tutarla kayıtlı bir işlem var mı?"""
    mid = db.musteri_bul(kayit["musteri"])
    if mid is None:
        return False
    tutar = sum(a * f for _, a, f in kayit["kalemler"]) if satis else kayit["tutar"]
    return db.tek("""SELECT COUNT(*) FROM islem WHERE musteri_id=? AND tur=? AND tarih=?
                     AND ABS(tutar - ?) < 0.01""",
                  mid, "SATIŞ" if satis else "TAHSİLAT", kayit["tarih"], round(tutar, 2)) > 0


def kaydet(db, satislar, tahsilatlar):
    """Okunan kayıtları tek seferde veritabanına yazar. Yeni oluşturulan müşteri sayısını döndürür.

    Excel'deki fiş numarası programda boşsa aynen kullanılır, doluysa sıradaki numara verilir.
    Önce numarası yazılı fişler numaralarını alır; numarasız fişler (ör. devir) sonra sıradaki
    boş numarayı alır, böylece Excel'deki fiş numaralarını kapmazlar.
    """
    onbellek, yeni = {}, 0
    kullanilan = {r[0] for r in db.sorgu("SELECT fis_no FROM islem WHERE fis_no IS NOT NULL")}

    def istenen_no(s):
        try:
            return int(float(s.get("fis") or 0))
        except (TypeError, ValueError):
            return 0

    numaralar = {}
    for i, s in enumerate(satislar):
        no = istenen_no(s)
        if no > 0 and no not in kullanilan:
            numaralar[i] = no
            kullanilan.add(no)
    for i in range(len(satislar)):
        if i not in numaralar:
            numaralar[i] = max(kullanilan, default=0) + 1
            kullanilan.add(numaralar[i])

    def musteri_id(ad):
        nonlocal yeni
        anahtar = kucuk(ad.strip())
        if anahtar not in onbellek:
            mid = db.musteri_bul(ad)
            if mid is None:
                mid = db.con.execute("INSERT INTO musteri (ad) VALUES (?)", (ad.strip(),)).lastrowid
                yeni += 1
            onbellek[anahtar] = mid
        return onbellek[anahtar]

    with db.con:
        for i, s in enumerate(satislar):
            toplam = round(sum(a * f for _, a, f in s["kalemler"]), 2)
            iid = db.con.execute(
                "INSERT INTO islem (musteri_id, tur, tarih, tutar, aciklama, fis_no) "
                "VALUES (?, 'SATIŞ', ?, ?, ?, ?)",
                (musteri_id(s["musteri"]), s["tarih"], toplam, s["aciklama"], numaralar[i])).lastrowid
            db.con.executemany(
                "INSERT INTO kalem (islem_id, urun, adet, birim_fiyat) VALUES (?, ?, ?, ?)",
                [(iid, u, a, f) for u, a, f in s["kalemler"]])
        for t in tahsilatlar:
            db.con.execute(
                "INSERT INTO islem (musteri_id, tur, tarih, tutar, aciklama) VALUES (?, 'TAHSİLAT', ?, ?, ?)",
                (musteri_id(t["musteri"]), t["tarih"], t["tutar"], t["aciklama"]))
    return yeni
