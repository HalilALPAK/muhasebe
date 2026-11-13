"""Cloudflare sunucusuyla eşitleme (laptop tarafı).

Her kayıt yerelde 'kirli' (gönderilecek) işaretiyle tutulur. Eşitlemede kirli kayıtlar parça parça
sunucuya gider; cevapta sunucunun, bu cihazın son gördüğü sürümden sonra değişen kayıtları gelir
ve yerele işlenir. İnternet yokken program normal çalışır, değişiklikler bekler.
Birleştirme kuralları sunucudadır (sunucu/src/index.js); burada yalnızca sonuç uygulanır.
"""
import json
import os
import platform
import queue
import sqlite3
import threading
import tkinter as tk
import urllib.error
import urllib.request
from datetime import datetime
from tkinter import ttk, messagebox

from muhasebe import FIRMA, KIRMIZI, YESIL, KOYU_TURUNCU

API = 1
GONDERIM = 400          # bir istekte en fazla bu kadar kayıt gönderilir
OTOMATIK_SURE = 60_000  # ms: değişiklik olmasa da bu aralıkla diğer cihazların değişikliklerine bakılır
VARSAYILAN_SUNUCU = ""  # yayınlanan Cloudflare adresi; ayarlarda boşsa bu önerilir


class BulutHatasi(Exception):
    pass


def istek(url, anahtar, yol, govde=None, zaman_asimi=60):
    veri = json.dumps(govde, ensure_ascii=False).encode("utf-8") if govde is not None else None
    r = urllib.request.Request(url.rstrip("/") + yol, data=veri, method="POST" if veri else "GET", headers={
        "Authorization": f"Bearer {anahtar}", "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "OgulTarimMuhasebe/1"})
    try:
        with urllib.request.urlopen(r, timeout=zaman_asimi) as y:
            return json.loads(y.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            mesaj = json.loads(e.read().decode("utf-8")).get("hata")
        except (ValueError, OSError):
            mesaj = None
        if e.code == 401:
            raise BulutHatasi("Sunucu anahtarı hatalı. Sunucu Ayarları'ndan kontrol edin.") from e
        raise BulutHatasi(mesaj or f"Sunucu hatası ({e.code})") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise BulutHatasi("Sunucuya ulaşılamadı. İnternet bağlantınızı kontrol edin.") from e
    except ValueError as e:
        raise BulutHatasi("Sunucudan geçersiz cevap geldi. Sunucu adresini kontrol edin.") from e


def durum_sor(url, anahtar):
    d = istek(url, anahtar, "/v1/durum", zaman_asimi=15)
    if d.get("uygulama") != "ogul_tarim":
        raise BulutHatasi("Bu adres Oğul Tarım sunucusu değil.")
    return d


# ---------------------------------------------------------------- gönderilecekleri toplama
def _kirlileri_topla(con, sinir):
    """Müşteriler önce gider (işlemler sunucuda müşterisini bulabilsin diye)."""
    d = {"musteri": [], "islem": [], "gider": [], "silinen": []}
    isaret = []
    for uuid, ad, tel, notlar, g in con.execute(
            "SELECT uuid, ad, COALESCE(telefon, ''), COALESCE(notlar, ''), guncelleme FROM musteri WHERE kirli = 1 LIMIT ?", (sinir,)):
        d["musteri"].append({"uuid": uuid, "ad": ad, "telefon": tel, "notlar": notlar, "guncelleme": g})
        isaret.append(("musteri", uuid, g))
    kalan = sinir - len(isaret)
    if kalan > 0 and not d["musteri"]:
        satirlar = con.execute("""SELECT i.id, i.uuid, m.uuid, i.tur, i.tarih, i.tutar, COALESCE(i.aciklama, ''), i.fis_no, i.guncelleme
                                  FROM islem i JOIN musteri m ON m.id = i.musteri_id WHERE i.kirli = 1 LIMIT ?""", (kalan,)).fetchall()
        for iid, uuid, mu, tur, t, tutar, ac, fis, g in satirlar:
            kalemler = [{"urun": u, "adet": a, "birim_fiyat": f} for u, a, f in con.execute(
                "SELECT urun, adet, birim_fiyat FROM kalem WHERE islem_id = ? ORDER BY id", (iid,))]
            d["islem"].append({"uuid": uuid, "musteri_uuid": mu, "tur": tur, "tarih": t, "tutar": tutar, "aciklama": ac,
                               "fis_no": fis, "guncelleme": g, "kalemler": kalemler})
            isaret.append(("islem", uuid, g))
        kalan = sinir - len(isaret)
        for uuid, t, kat, tutar, ac, g in con.execute(
                "SELECT uuid, tarih, COALESCE(kategori, ''), tutar, COALESCE(aciklama, ''), guncelleme FROM gider WHERE kirli = 1 LIMIT ?",
                (max(kalan, 0),)):
            d["gider"].append({"uuid": uuid, "tarih": t, "kategori": kat, "tutar": tutar, "aciklama": ac, "guncelleme": g})
            isaret.append(("gider", uuid, g))
        kalan = sinir - len(isaret)
        if not d["islem"]:                     # silmeler, eklemeler bittikten sonra
            for uuid, tablo, z in con.execute("SELECT uuid, tablo, zaman FROM silinen WHERE kirli = 1 LIMIT ?", (max(kalan, 0),)):
                d["silinen"].append({"uuid": uuid, "tablo": tablo, "zaman": z})
                isaret.append(("silinen", uuid, z))
    return d, isaret


# ---------------------------------------------------------------- gelenleri uygulama
def _musteri_uygula(con, m):
    r = con.execute("SELECT id, guncelleme, kirli FROM musteri WHERE uuid = ?", (m["uuid"],)).fetchone()
    if r and r[2] == 1 and r[1] > m["guncelleme"]:
        return                                 # yerelde daha yeni, henüz gönderilmemiş değişiklik var
    if m["silindi"]:
        if r:
            if con.execute("SELECT COUNT(*) FROM islem WHERE musteri_id = ? AND kirli = 1", (r[0],)).fetchone()[0]:
                return                         # gönderilmemiş işlemi var: silme, sonraki eşitlemede geri gelir
            con.execute("DELETE FROM musteri WHERE id = ?", (r[0],))
        con.execute("INSERT OR REPLACE INTO silinen (uuid, tablo, zaman, kirli) VALUES (?, 'musteri', ?, 0)",
                    (m["uuid"], m["guncelleme"]))
    elif r:
        con.execute("UPDATE musteri SET ad = ?, telefon = ?, notlar = ?, guncelleme = ?, kirli = 0 WHERE id = ?",
                    (m["ad"], m["telefon"], m["notlar"], m["guncelleme"], r[0]))
    else:
        con.execute("DELETE FROM silinen WHERE uuid = ?", (m["uuid"],))
        con.execute("INSERT INTO musteri (ad, telefon, notlar, uuid, guncelleme, kirli) VALUES (?, ?, ?, ?, ?, 0)",
                    (m["ad"], m["telefon"], m["notlar"], m["uuid"], m["guncelleme"]))


def _islemleri_uygula(con, islemler, esleme, fis_degisen):
    uygulanacak = []
    for s in islemler:
        r = con.execute("SELECT id, guncelleme, kirli FROM islem WHERE uuid = ?", (s["uuid"],)).fetchone()
        if not (r and r[2] == 1 and r[1] > s["guncelleme"]):
            uygulanacak.append((s, r))
    # gelenlerin fiş numaraları önce boşaltılır ki numaralar yer değiştirirken çakışma olmasın
    con.executemany("UPDATE islem SET fis_no = NULL WHERE uuid = ?", [(s["uuid"],) for s, r in uygulanacak if r])
    for s, r in uygulanacak:
        if s["silindi"]:
            if r:
                con.execute("DELETE FROM islem WHERE id = ?", (r[0],))
            con.execute("INSERT OR REPLACE INTO silinen (uuid, tablo, zaman, kirli) VALUES (?, 'islem', ?, 0)",
                        (s["uuid"], s["guncelleme"]))
            continue
        mu = s["musteri_uuid"]
        for _ in range(10):
            mu = esleme.get(mu, mu) if mu in esleme else mu
        m = con.execute("SELECT id FROM musteri WHERE uuid = ?", (mu,)).fetchone()
        if not m:
            raise BulutHatasi("Sunucudan gelen bir işlemin müşterisi bulunamadı. Tekrar eşitleyin.")
        fis = s["fis_no"]
        if fis is not None:
            cakisan = con.execute("SELECT id FROM islem WHERE fis_no = ? AND uuid <> ?", (fis, s["uuid"])).fetchone()
            if cakisan:                        # yerelde aynı numaralı, henüz gönderilmemiş fiş: ona yeni numara
                yeni = con.execute("SELECT COALESCE(MAX(fis_no), 0) + 1 FROM islem").fetchone()[0]
                con.execute("UPDATE islem SET fis_no = ? WHERE id = ?", (yeni, cakisan[0]))
                fis_degisen.append((fis, yeni))
        if r:
            iid = r[0]
            con.execute("""UPDATE islem SET musteri_id = ?, tur = ?, tarih = ?, tutar = ?, aciklama = ?, fis_no = ?,
                           guncelleme = ?, kirli = 0 WHERE id = ?""",
                        (m[0], s["tur"], s["tarih"], s["tutar"], s["aciklama"], fis, s["guncelleme"], iid))
            con.execute("DELETE FROM kalem WHERE islem_id = ?", (iid,))
        else:
            con.execute("DELETE FROM silinen WHERE uuid = ?", (s["uuid"],))
            iid = con.execute("""INSERT INTO islem (musteri_id, tur, tarih, tutar, aciklama, fis_no, uuid, guncelleme, kirli)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                              (m[0], s["tur"], s["tarih"], s["tutar"], s["aciklama"], fis, s["uuid"], s["guncelleme"])).lastrowid
        con.executemany("INSERT INTO kalem (islem_id, urun, adet, birim_fiyat) VALUES (?, ?, ?, ?)",
                        [(iid, k["urun"], k["adet"], k["birim_fiyat"]) for k in s["kalemler"]])


def _gider_uygula(con, x):
    r = con.execute("SELECT id, guncelleme, kirli FROM gider WHERE uuid = ?", (x["uuid"],)).fetchone()
    if r and r[2] == 1 and r[1] > x["guncelleme"]:
        return
    if x["silindi"]:
        if r:
            con.execute("DELETE FROM gider WHERE id = ?", (r[0],))
        con.execute("INSERT OR REPLACE INTO silinen (uuid, tablo, zaman, kirli) VALUES (?, 'gider', ?, 0)", (x["uuid"], x["guncelleme"]))
    elif r:
        con.execute("UPDATE gider SET tarih = ?, kategori = ?, tutar = ?, aciklama = ?, guncelleme = ?, kirli = 0 WHERE id = ?",
                    (x["tarih"], x["kategori"], x["tutar"], x["aciklama"], x["guncelleme"], r[0]))
    else:
        con.execute("DELETE FROM silinen WHERE uuid = ?", (x["uuid"],))
        con.execute("INSERT INTO gider (tarih, kategori, tutar, aciklama, uuid, guncelleme, kirli) VALUES (?, ?, ?, ?, ?, ?, 0)",
                    (x["tarih"], x["kategori"], x["tutar"], x["aciklama"], x["uuid"], x["guncelleme"]))


def _uygula(con, c, isaret, fis_degisen):
    """Sunucu cevabını tek işlemde yerele yazar. Eşitlemenin kendi yazdıkları 'kirli' işaretlenmez."""
    con.execute("BEGIN IMMEDIATE")
    try:
        con.execute("UPDATE senkron_kilit SET aktif = 1")
        # gönderilenler: gönderildikten sonra yeniden değişmediyse artık temiz
        for tablo, uuid, g in isaret:
            alan = "zaman" if tablo == "silinen" else "guncelleme"
            con.execute(f"UPDATE {tablo} SET kirli = 0 WHERE uuid = ? AND {alan} = ? AND kirli = 1", (uuid, g))
        for m in c.get("musteri", []) + c.get("bagli_musteri", []):
            _musteri_uygula(con, m)
        esleme = {e["eski"]: e["yeni"] for e in c.get("esleme", [])}
        for eski, yeni in esleme.items():      # sunucuda birleştirilen aynı isimli müşteriler
            e = con.execute("SELECT id FROM musteri WHERE uuid = ?", (eski,)).fetchone()
            y = con.execute("SELECT id FROM musteri WHERE uuid = ?", (yeni,)).fetchone()
            if e and y:
                con.execute("UPDATE islem SET musteri_id = ? WHERE musteri_id = ?", (y[0], e[0]))
                con.execute("DELETE FROM musteri WHERE id = ?", (e[0],))
        _islemleri_uygula(con, c.get("islem", []), esleme, fis_degisen)
        for x in c.get("gider", []):
            _gider_uygula(con, x)
        con.execute("INSERT OR REPLACE INTO ayar (anahtar, deger) VALUES ('son_surum', ?)", (str(c["son_surum"]),))
        con.execute("UPDATE senkron_kilit SET aktif = 0")
        con.commit()
    except Exception:
        con.rollback()
        raise


def esitle(db_yolu, url, anahtar, cihaz):
    """Bekleyen değişiklikleri gönderir, sunucudaki yenileri alır. Dönüş: özet sözlüğü."""
    con = sqlite3.connect(db_yolu, timeout=30, isolation_level=None)
    con.execute("PRAGMA foreign_keys = ON")
    ozet = {"gonderilen": 0, "alinan": 0, "fis_degisen": []}
    try:
        for _ in range(500):                   # her turda en fazla GONDERIM kayıt gider, 1000 kayıt gelir
            son = int((con.execute("SELECT deger FROM ayar WHERE anahtar = 'son_surum'").fetchone() or ["0"])[0] or 0)
            giden, isaret = _kirlileri_topla(con, GONDERIM)
            c = istek(url, anahtar, "/v1/esitle", {"api": API, "cihaz": cihaz, "son_surum": son, "degisiklikler": giden})
            if c.get("sunucu_sifirlandi"):     # sunucu verisi silinmiş: bu cihazdaki her şey yeniden yüklenir
                con.execute("BEGIN IMMEDIATE")
                con.execute("UPDATE senkron_kilit SET aktif = 1")
                for t in ("musteri", "islem", "gider", "silinen"):
                    con.execute(f"UPDATE {t} SET kirli = 1")
                con.execute("INSERT OR REPLACE INTO ayar (anahtar, deger) VALUES ('son_surum', '0')")
                con.execute("UPDATE senkron_kilit SET aktif = 0")
                con.commit()
                continue
            _uygula(con, c, isaret, ozet["fis_degisen"])
            ozet["gonderilen"] += len(isaret)
            ozet["alinan"] += len(c.get("musteri", [])) + len(c.get("islem", [])) + len(c.get("gider", []))
            ozet["fis_degisen"] += [(f["eski"], f["yeni"]) for f in c["rapor"]["fis_degisen"]]
            if not isaret and not c.get("daha_var"):
                break
        return ozet
    finally:
        con.close()


# ---------------------------------------------------------------- arka plan eşitleyici
class BulutEsitleyici:
    """Değişiklikten birkaç saniye sonra ve her dakika arka planda eşitler; durumu başlıkta gösterir."""

    def __init__(self, uyg):
        self.uyg = uyg
        self.olaylar = queue.Queue()
        self.calisiyor = False
        self.bekleyen = False
        self._zamanlayici = None
        self.durum_lbl = None
        self.son_durum = ("", "#8a7a6a")
        uyg.after(300, self._dinle)
        uyg.after(1500, self.tetikle)
        uyg.after(OTOMATIK_SURE, self._periyodik)

    def ayarli(self):
        return bool(self.uyg.db.ayar("sunucu_url") and self.uyg.db.ayar("sunucu_anahtar"))

    def tetikle(self, gecikme=0):
        if self._zamanlayici:
            self.uyg.after_cancel(self._zamanlayici)
        self._zamanlayici = self.uyg.after(gecikme, self._baslat)

    def _periyodik(self):
        self.tetikle()
        self.uyg.after(OTOMATIK_SURE, self._periyodik)

    def _baslat(self):
        self._zamanlayici = None
        if self.calisiyor:
            self.bekleyen = True
            return
        if not self.ayarli():
            self._goster("☁ Sunucu ayarlanmadı", "#8a7a6a")
            return
        db = self.uyg.db
        url, anahtar = db.ayar("sunucu_url"), db.ayar("sunucu_anahtar")
        cihaz = db.ayar("cihaz", platform.node() or "laptop")
        self.calisiyor = True
        self._goster("☁ Eşitleniyor…", KOYU_TURUNCU)

        def calis():
            try:
                self.olaylar.put(("tamam", esitle(db.yol, url, anahtar, cihaz)))
            except BulutHatasi as e:
                self.olaylar.put(("hata", str(e)))
            except Exception as e:             # beklenmeyen hata programı durdurmasın
                self.olaylar.put(("hata", f"Eşitleme hatası: {e}"))
        threading.Thread(target=calis, daemon=True).start()

    def _goster(self, metin, renk):
        self.son_durum = (metin, renk)
        if self.durum_lbl and self.durum_lbl.winfo_exists():
            self.durum_lbl.config(text=metin, fg=renk)

    def _dinle(self):
        try:
            while True:
                tur, veri = self.olaylar.get_nowait()
                self.calisiyor = False
                bekleyen = self.uyg.db.bekleyen_sayisi()
                if tur == "tamam":
                    if veri["alinan"]:
                        self.uyg.yenile_ekranlar()
                    ek = f" · {bekleyen} bekleyen" if bekleyen else ""
                    self._goster(f"☁ Eşitlendi {datetime.now():%H:%M}{ek}", YESIL)
                    if veri["fis_degisen"]:
                        messagebox.showinfo("Eşitleme", "Başka cihazda aynı numara kullanıldığı için fiş numarası değişti:\n"
                                            + "\n".join(f"Fiş {a} → Fiş {b}" for a, b in veri["fis_degisen"]))
                else:
                    self._goster(f"☁ Çevrimdışı · {bekleyen} bekleyen" if "ulaşılamadı" in veri else f"☁ {veri}", KIRMIZI)
                if self.bekleyen:
                    self.bekleyen = False
                    self.tetikle(500)
        except queue.Empty:
            pass
        self.uyg.after(300, self._dinle)


class SunucuAyarPenceresi(tk.Toplevel):
    def __init__(self, uyg):
        super().__init__(uyg)
        self.uyg, self.db = uyg, uyg.db
        self.title(f"{FIRMA} - Sunucu Ayarları")
        self.resizable(False, False)
        self.transient(uyg)
        self.grab_set()
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both")
        ttk.Label(f, text="Sunucu (Cloudflare) Ayarları", style="Baslik.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(f, wraplength=470, justify="left", foreground="#6A5A4A", text=(
            "Laptop ve telefon aynı sunucu adresini ve anahtarı kullanınca kayıtlar internet üzerinden "
            "otomatik eşitlenir. İnternet yokken çalışmaya devam edersiniz; değişiklikler bağlantı gelince gönderilir.\n"
            "İlk eşitlemede bu bilgisayardaki tüm kayıtlar sunucuya yüklenir.")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))
        self.url = tk.StringVar(self, self.db.ayar("sunucu_url") or VARSAYILAN_SUNUCU)
        self.anahtar = tk.StringVar(self, self.db.ayar("sunucu_anahtar"))
        self.cihaz = tk.StringVar(self, self.db.ayar("cihaz", platform.node() or "laptop"))
        for r, (etiket, var, gizli) in enumerate([("Sunucu adresi", self.url, False), ("Sunucu anahtarı", self.anahtar, True),
                                                  ("Bu cihazın adı", self.cihaz, False)], start=2):
            ttk.Label(f, text=etiket).grid(row=r, column=0, sticky="w", pady=4)
            ttk.Entry(f, textvariable=var, width=52, show="•" if gizli else "").grid(row=r, column=1, pady=4, padx=(10, 0))
        self.durum = ttk.Label(f, text=f"Bekleyen değişiklik: {self.db.bekleyen_sayisi()}", wraplength=470, justify="left")
        self.durum.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
        alt = ttk.Frame(f)
        alt.grid(row=6, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(alt, text="Bağlantıyı Test Et", command=self.test).pack(side="left")
        ttk.Button(alt, text="Kaydet ve Eşitle", style="Vurgu.TButton", command=self.kaydet).pack(side="left", padx=(8, 0))

    def _degerler(self):
        url = self.url.get().strip().rstrip("/")
        if url and not url.startswith(("https://", "http://")):
            url = "https://" + url
        return url, self.anahtar.get().strip()

    def test(self):
        url, anahtar = self._degerler()
        if not url or not anahtar:
            self.durum.config(text="Adres ve anahtarı girin.", foreground=KIRMIZI)
            return
        self.config(cursor="watch")
        self.update()
        try:
            d = durum_sor(url, anahtar)
            self.durum.config(foreground=YESIL, text=(
                f"Bağlantı başarılı. Sunucuda {d['musteri']} müşteri, {d['islem']} işlem, {d['gider']} gider var."))
        except BulutHatasi as e:
            self.durum.config(text=str(e), foreground=KIRMIZI)
        finally:
            self.config(cursor="")

    def kaydet(self):
        url, anahtar = self._degerler()
        if url != self.db.ayar("sunucu_url"):
            # yeni sunucu: her şey baştan gönderilir ve alınır
            self.db.con.execute("UPDATE senkron_kilit SET aktif = 1")
            for t in ("musteri", "islem", "gider", "silinen"):
                self.db.con.execute(f"UPDATE {t} SET kirli = 1")
            self.db.con.execute("UPDATE senkron_kilit SET aktif = 0")
            self.db.ayar_yaz("son_surum", 0)
        self.db.ayar_yaz("sunucu_url", url)
        self.db.ayar_yaz("sunucu_anahtar", anahtar)
        self.db.ayar_yaz("cihaz", self.cihaz.get().strip() or "laptop")
        self.destroy()
        self.uyg.bulut.tetikle()
