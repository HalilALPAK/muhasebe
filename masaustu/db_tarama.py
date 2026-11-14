"""Masaüstünde (ve alt klasörlerinde) bu programa ait başka muhasebe veritabanlarını bulur ve
kayıtlarını programın veritabanına aktarır. Aktarılanlar 'gönderilecek' işaretlenir; böylece
sonraki eşitlemede sunucuya da gider.

Bulunan dosyaya dokunulmaz: geçici bir kopyası açılıp okunur.
"""
import os
import shutil
import sqlite3
import tempfile

from muhasebe import DB, kucuk

EN_FAZLA_DERINLIK = 3
EN_BUYUK_BOYUT = 300 * 1024 * 1024
ATLANAN = {"node_modules", ".git", "build", "dist", ".dart_tool", ".wrangler", "Yedekler", "__pycache__", "AppData", ".gradle"}


def aday_klasorler():
    ev = os.path.expanduser("~")
    adaylar = [os.path.join(ev, "Desktop"), os.path.join(ev, "Masaüstü")]
    for od in {os.environ.get("OneDrive"), os.environ.get("OneDriveConsumer"), os.path.join(ev, "OneDrive")}:
        if od:
            adaylar += [os.path.join(od, "Desktop"), os.path.join(od, "Masaüstü")]
    goruldu, sonuc = set(), []
    for a in adaylar:
        if os.path.isdir(a) and os.path.normcase(os.path.realpath(a)) not in goruldu:
            goruldu.add(os.path.normcase(os.path.realpath(a)))
            sonuc.append(a)
    return sonuc


def _bizim_mi(yol):
    """Bu programın veritabanıysa (müşteri, işlem ve ürün tabloları) içindeki sayıları döndürür."""
    try:
        with open(yol, "rb") as f:
            if f.read(16) != b"SQLite format 3\x00":
                return None
        con = sqlite3.connect(f"file:{yol}?mode=ro", uri=True, timeout=2)
        try:
            tablolar = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if not {"musteri", "islem", "kalem"} <= tablolar:
                return None
            if not {"ad"} <= {r[1] for r in con.execute("PRAGMA table_info(musteri)")}:
                return None
            if not {"musteri_id", "tur", "tarih", "tutar"} <= {r[1] for r in con.execute("PRAGMA table_info(islem)")}:
                return None
            musteri = con.execute("SELECT COUNT(*) FROM musteri").fetchone()[0]
            islem = con.execute("SELECT COUNT(*) FROM islem").fetchone()[0]
            return (musteri, islem) if musteri or islem else None
        finally:
            con.close()
    except (OSError, sqlite3.Error):
        return None


def tara(haric_yol, klasorler=None):
    """[(yol, müşteri sayısı, işlem sayısı, değişme zamanı)] — programın kendi veritabanı hariç."""
    haric = os.path.normcase(os.path.realpath(haric_yol))
    bulunan = []
    for kok in klasorler if klasorler is not None else aday_klasorler():
        kok_derinlik = kok.rstrip(os.sep).count(os.sep)
        for klasor, alt, dosyalar in os.walk(kok):
            if klasor.count(os.sep) - kok_derinlik >= EN_FAZLA_DERINLIK:
                alt[:] = []
            alt[:] = [a for a in alt if a not in ATLANAN and not a.startswith(".")]
            for d in dosyalar:
                if not d.lower().endswith((".db", ".sqlite", ".sqlite3")):
                    continue
                yol = os.path.join(klasor, d)
                if os.path.normcase(os.path.realpath(yol)) == haric:
                    continue
                try:
                    st = os.stat(yol)
                except OSError:
                    continue
                if st.st_size > EN_BUYUK_BOYUT:
                    continue
                sayilar = _bizim_mi(yol)
                if sayilar:
                    bulunan.append((yol, sayilar[0], sayilar[1], int(st.st_mtime)))
    return bulunan


def ice_aktar(hedef, kaynak_yol):
    """Kaynak veritabanındaki kayıtları hedef DB'ye ekler. Dönüş: rapor sözlüğü.

    - Aynı kimlikli (uuid) kayıt hedefte varsa atlanır.
    - Müşteri aynı isimle hedefte varsa onunla birleşir (boş telefon/not doldurulur).
    - Aynı müşteri, tarih, tür ve tutarlı işlem zaten varsa tekrar eklenmez.
    - Fiş numarası hedefte kullanılıyorsa sıradaki boş numara verilir.
    """
    rapor = {"musteri": 0, "birlesen": 0, "islem": 0, "atlanan": 0, "gider": 0, "fis_degisen": []}
    gecici = tempfile.mkdtemp()
    kopya = os.path.join(gecici, "kaynak.db")
    shutil.copy2(kaynak_yol, kopya)
    kaynak = DB(kopya)                         # eski yapıdaysa kopya yeni yapıya geçer (uuid eklenir)
    con = hedef.con
    try:
        harita = {}
        for kid, uuid, ad, tel, notlar, g in kaynak.sorgu(
                "SELECT id, uuid, ad, COALESCE(telefon, ''), COALESCE(notlar, ''), guncelleme FROM musteri"):
            r = con.execute("SELECT id FROM musteri WHERE uuid = ?", (uuid,)).fetchone()
            if r:
                harita[kid] = r[0]
                continue
            mevcut = hedef.musteri_bul(ad)
            if mevcut:
                harita[kid] = mevcut
                _, mad, mtel, mnot = hedef.musteri(mevcut)
                if (tel and not mtel) or (notlar and not mnot):
                    con.execute("UPDATE musteri SET telefon = ?, notlar = ? WHERE id = ?", (mtel or tel, mnot or notlar, mevcut))
                rapor["birlesen"] += 1
            else:
                harita[kid] = con.execute("INSERT INTO musteri (ad, telefon, notlar, uuid, guncelleme) VALUES (?, ?, ?, ?, ?)",
                                          (ad, tel, notlar, uuid, g)).lastrowid
                rapor["musteri"] += 1

        def imza(c, iid, tur, tarih, tutar, ac):
            """Aynı işlemi tanımak için: eski yapıdaki dosyalarda kimlik her açılışta yeniden üretildiği
            ve fiş numarası değişmiş olabileceği için içerik karşılaştırılır."""
            if tur == "SATIŞ":
                ek = tuple(sorted((u, round(a, 3), round(f, 2)) for u, a, f in c.execute(
                    "SELECT urun, adet, birim_fiyat FROM kalem WHERE islem_id = ?", (iid,))))
            else:
                ek = ac
            return (tur, tarih, round(tutar, 2), ek)

        # hedefte önceden bulunan işlemler; her biri en fazla bir kaynak işlemiyle eşleşir
        mevcut = {}
        for iid, mid, tur, tarih, tutar, ac in con.execute(
                "SELECT id, musteri_id, tur, tarih, tutar, COALESCE(aciklama, '') FROM islem"):
            mevcut.setdefault((mid,) + imza(con, iid, tur, tarih, tutar, ac), []).append(iid)
        # çakışan fişler iki veritabanındaki en büyük numaranın arkasından numaralanır (zincirleme kayma olmasın)
        sonraki_fis = max(hedef.sonraki_fis_no(), kaynak.sonraki_fis_no())

        for kid, uuid, mid, tur, tarih, tutar, ac, fis, g in kaynak.sorgu(
                "SELECT id, uuid, musteri_id, tur, tarih, tutar, COALESCE(aciklama, ''), fis_no, guncelleme FROM islem ORDER BY id"):
            hedef_mid = harita.get(mid)
            if hedef_mid is None or con.execute("SELECT 1 FROM islem WHERE uuid = ?", (uuid,)).fetchone():
                rapor["atlanan"] += 1
                continue
            eslesen = mevcut.get((hedef_mid,) + imza(kaynak.con, kid, tur, tarih, tutar, ac))
            if eslesen:
                eslesen.pop()                  # aynı işlem daha önce aktarılmış
                rapor["atlanan"] += 1
                continue
            if tur == "SATIŞ" and (fis is None or con.execute("SELECT 1 FROM islem WHERE fis_no = ?", (fis,)).fetchone()):
                if fis is not None:
                    rapor["fis_degisen"].append((fis, sonraki_fis))
                fis, sonraki_fis = sonraki_fis, sonraki_fis + 1
            iid = con.execute("""INSERT INTO islem (musteri_id, tur, tarih, tutar, aciklama, fis_no, uuid, guncelleme)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                              (hedef_mid, tur, tarih, tutar, ac, fis if tur == "SATIŞ" else None, uuid, g)).lastrowid
            con.executemany("INSERT INTO kalem (islem_id, urun, adet, birim_fiyat) VALUES (?, ?, ?, ?)",
                            kaynak.sorgu("SELECT ?, urun, adet, birim_fiyat FROM kalem WHERE islem_id = ? ORDER BY id", iid, kid))
            rapor["islem"] += 1

        for uuid, tarih, kat, tutar, ac, g in kaynak.sorgu(
                "SELECT uuid, tarih, COALESCE(kategori, ''), tutar, COALESCE(aciklama, ''), guncelleme FROM gider"):
            if con.execute("SELECT 1 FROM gider WHERE uuid = ? OR (tarih = ? AND kategori = ? AND ABS(tutar - ?) < 0.01)",
                           (uuid, tarih, kat, tutar)).fetchone():
                continue
            con.execute("INSERT INTO gider (tarih, kategori, tutar, aciklama, uuid, guncelleme) VALUES (?, ?, ?, ?, ?, ?)",
                        (tarih, kat, tutar, ac, uuid, g))
            rapor["gider"] += 1
        con.commit()
        return rapor
    except Exception:
        con.rollback()
        raise
    finally:
        kaynak.con.close()
        shutil.rmtree(gecici, ignore_errors=True)


# ---------------------------------------------------------------- program içinden kullanım
def _sorulanlar(db):
    import json
    try:
        return json.loads(db.ayar("taranan_db", "{}"))
    except ValueError:
        return {}


def _isaretle(db, bulunanlar):
    import json
    s = _sorulanlar(db)
    for yol, _, _, mtime in bulunanlar:
        s[os.path.normcase(os.path.realpath(yol))] = mtime
    db.ayar_yaz("taranan_db", json.dumps(s, ensure_ascii=False))


def tara_ve_sor(uyg, elle=False):
    """Masaüstünü arka planda tarar; daha önce sorulmamış veritabanı bulursa aktarmayı önerir.
    elle=True ise daha önce sorulanlar da gösterilir ve hiçbir şey bulunmazsa bilgi verilir."""
    import queue
    import threading
    from tkinter import messagebox

    sonuc = queue.Queue()
    threading.Thread(target=lambda: sonuc.put(tara(uyg.db.yol)), daemon=True).start()

    def bekle():
        try:
            bulunan = sonuc.get_nowait()
        except queue.Empty:
            uyg.after(300, bekle)
            return
        sorulan = _sorulanlar(uyg.db)
        if not elle:
            bulunan = [b for b in bulunan if sorulan.get(os.path.normcase(os.path.realpath(b[0]))) != b[3]]
        if not bulunan:
            if elle:
                messagebox.showinfo("Veritabanı Arama", "Masaüstünde aktarılacak başka muhasebe veritabanı bulunamadı.")
            return
        liste = "\n".join(f"• {yol}\n   {m} müşteri, {i} işlem" for yol, m, i, _ in bulunan[:6])
        if messagebox.askyesno("Muhasebe veritabanı bulundu", (
                f"Masaüstünde bu programa ait {len(bulunan)} veritabanı bulundu:\n\n{liste}\n\n"
                "Bu kayıtlar programa aktarılsın ve sunucuya gönderilsin mi?\n"
                "Aynı müşteriler birleştirilir, aynı fişler ikinci kez eklenmez. Bulunan dosyalara dokunulmaz.")):
            uyg.db.yedek_al("aktarim_oncesi")
            toplam = {"musteri": 0, "birlesen": 0, "islem": 0, "atlanan": 0, "gider": 0, "fis_degisen": []}
            hatalar = []
            for yol, *_ in bulunan:
                try:
                    r = ice_aktar(uyg.db, yol)
                    for k in toplam:
                        toplam[k] += r[k]
                except Exception as e:
                    hatalar.append(f"{yol}: {e}")
            mesaj = (f"{toplam['musteri']} yeni müşteri, {toplam['islem']} işlem, {toplam['gider']} gider aktarıldı.\n"
                     f"{toplam['birlesen']} müşteri mevcut müşteriyle birleşti, {toplam['atlanan']} işlem zaten vardı.")
            if toplam["fis_degisen"]:
                mesaj += "\n\nNumarası dolu olduğu için değişen fişler:\n" + ", ".join(f"{a}→{b}" for a, b in toplam["fis_degisen"][:30])
            if hatalar:
                mesaj += "\n\nAktarılamayanlar:\n" + "\n".join(hatalar)
            uyg.degisti()                      # ekranları yenile ve sunucuya gönder
            messagebox.showinfo("Aktarım tamam", mesaj + "\n\nKayıtlar internet bağlantısı olduğunda sunucuya gönderilecek.")
        _isaretle(uyg.db, bulunan)

    uyg.after(300, bekle)
