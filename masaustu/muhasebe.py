"""Basit Muhasebe Programı - Müşteri bazlı satış, tahsilat, gider ve bilanço takibi."""
import math
import os
import re
import sqlite3
import sys
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime, date, timedelta
from tkinter import ttk, messagebox, filedialog

if getattr(sys, "frozen", False):            # .exe: veriler exe'nin yanında, logo exe'nin içinde
    KLASOR, KAYNAK = os.path.dirname(sys.executable), sys._MEIPASS
else:
    KLASOR = KAYNAK = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(KLASOR, "muhasebe.db")
LOGO_PATH = os.path.join(KAYNAK, "logo.jpg")
FIRMA = "OĞUL TARIM"

KIRMIZI, YESIL = "#b00020", "#1b7f2a"
TURUNCU, KOYU_TURUNCU, ACIK_TURUNCU = "#F17E01", "#C46400", "#FEF2E6"
ZEMIN = "#FBF8F5"
VARSAYILAN_GIDERLER = ["Kira", "Elektrik", "Su", "Doğalgaz", "Maaş", "Mal Alımı",
                       "Yakıt", "Vergi", "İnternet / Telefon", "Diğer"]


# ---------------------------------------------------------------- yardımcılar
def para(x):
    """1234.5 -> '1.234,50 ₺'"""
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} ₺"


def kisa(x):
    """Grafik ekseni için kısa sayı: 12500 -> '12,5 B'"""
    for bolen, ek in ((1e6, " Mn"), (1e3, " B")):
        if abs(x) >= bolen:
            return f"{x / bolen:.1f}".rstrip("0").rstrip(".").replace(".", ",") + ek
    return f"{x:.0f}"


def sayi_oku(metin):
    """'1.234,50' veya '1234.50' gibi girişleri float'a çevirir."""
    metin = metin.strip().replace(" ", "").replace("₺", "")
    if not metin:
        raise ValueError
    if "," in metin:
        metin = metin.replace(".", "").replace(",", ".")
    return float(metin)


def tarih_oku(metin):
    """'GG.AA.YYYY' (veya iki haneli yıl 'GG.AA.YY') -> 'YYYY-AA-GG'"""
    try:
        return datetime.strptime(metin.strip(), "%d.%m.%Y").date().isoformat()
    except ValueError:
        return datetime.strptime(metin.strip(), "%d.%m.%y").date().isoformat()


def tarih_goster(iso):
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y")


def kucuk(s):
    """Türkçe uyumlu küçük harfe çevirme (I->ı, İ->i)."""
    return s.replace("I", "ı").replace("İ", "i").lower()


def tablo(ana, kolonlar, agac=False):
    """Kaydırma çubuklu Treeview. kolonlar: [(anahtar, başlık, genişlik, hizalama), ...]"""
    kap = ttk.Frame(ana)
    tv = ttk.Treeview(kap, columns=[k[0] for k in kolonlar],
                      show="tree headings" if agac else "headings")
    for anahtar, baslik, genislik, hiza in kolonlar:
        tv.heading(anahtar, text=baslik)
        tv.column(anahtar, width=genislik, anchor=hiza)
    sb = ttk.Scrollbar(kap, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return kap, tv


def logo_yukle(kok, boyut):
    """Logoyu verilen boyuta küçültüp Tk görseli olarak döndürür (Pillow yoksa None)."""
    try:
        from PIL import Image, ImageTk
        im = Image.open(LOGO_PATH).convert("RGB")
        im.thumbnail((boyut, boyut), Image.LANCZOS)
        return ImageTk.PhotoImage(im, master=kok)
    except Exception:
        return None


def tema_uygula(kok):
    """Logodaki turuncuya uygun renk teması."""
    kok.configure(bg=ZEMIN)
    kok.option_add("*Toplevel.background", ZEMIN)
    stil = ttk.Style(kok)
    stil.theme_use("clam")
    stil.configure(".", background=ZEMIN, font=("Segoe UI", 10))
    stil.configure("TLabelframe", background=ZEMIN, bordercolor="#E6D5C3")
    stil.configure("TLabelframe.Label", background=ZEMIN, foreground=KOYU_TURUNCU,
                   font=("Segoe UI", 9, "bold"))
    stil.configure("TButton", padding=(10, 5), background="white", bordercolor="#D9C3AC",
                   lightcolor="white", darkcolor="#E9DCCF")
    stil.map("TButton", background=[("disabled", "#F3EFEB"), ("pressed", "#FBDDBD"),
                                    ("active", ACIK_TURUNCU)])
    for ad, yazi, bosluk in (("Vurgu.TButton", ("Segoe UI", 10, "bold"), (10, 5)),
                             ("Buyuk.TButton", ("Segoe UI", 26, "bold"), (30, 26))):
        stil.configure(ad, background=TURUNCU, foreground="white", bordercolor=KOYU_TURUNCU,
                       lightcolor=TURUNCU, darkcolor=KOYU_TURUNCU, font=yazi, padding=bosluk)
        stil.map(ad, background=[("disabled", "#F6CFA3"), ("pressed", KOYU_TURUNCU), ("active", "#FF8C14")],
                 foreground=[("disabled", "white")])
    stil.configure("Treeview", rowheight=25, background="white", fieldbackground="white",
                   bordercolor="#E6D5C3")
    stil.map("Treeview", background=[("selected", TURUNCU)], foreground=[("selected", "white")])
    stil.configure("Treeview.Heading", background=ACIK_TURUNCU, foreground="#5A3A12",
                   font=("Segoe UI", 9, "bold"), bordercolor="#E6D5C3", lightcolor=ACIK_TURUNCU)
    stil.map("Treeview.Heading", background=[("active", "#FBDDBD")])
    stil.configure("TNotebook", background=ZEMIN, bordercolor="#E6D5C3")
    stil.configure("TNotebook.Tab", padding=(14, 5), background="#F1E4D6", bordercolor="#E6D5C3")
    stil.map("TNotebook.Tab", background=[("selected", TURUNCU)], foreground=[("selected", "white")])
    for s in ("TEntry", "TCombobox"):
        stil.configure(s, fieldbackground="white", bordercolor="#D9C3AC", lightcolor="white")
        stil.map(s, bordercolor=[("focus", TURUNCU)], lightcolor=[("focus", "#FBDDBD")])
    stil.map("TCombobox", fieldbackground=[("readonly", "white")],
             selectbackground=[("readonly", "white")], selectforeground=[("readonly", "#3A2A1A")])
    stil.configure("Baslik.TLabel", font=("Segoe UI", 15, "bold"), foreground="#3A2A1A")
    stil.configure("Bakiye.TLabel", font=("Segoe UI", 12, "bold"))


# ---------------------------------------------------------------- tarih kutusu
class TarihGiris(ttk.Entry):
    """GG.AA.YYYY tarih kutusu: rakam yazdıkça noktalar kendiliğinden eklenir (06112026 -> 06.11.2026).

    Nokta elle de yazılabilir; tek haneli gün/aydan sonra yazılan nokta başına 0 ekler (6. -> 06.).
    """
    AYRACLAR = {"period", "slash", "minus", "comma", "KP_Decimal", "KP_Divide", "KP_Subtract"}

    def __init__(self, ana, **kw):
        super().__init__(ana, **kw)
        self.bind("<KeyPress>", self._tus)
        self.bind("<KeyRelease>", self._duzenle)

    @staticmethod
    def _bicimle(rakam):
        return rakam[:2] + ("." + rakam[2:4] if len(rakam) > 2 else "") + ("." + rakam[4:] if len(rakam) > 4 else "")

    def _yaz(self, rakam, imlec_rakam, sona_nokta=False):
        metin = self._bicimle(rakam) + ("." if sona_nokta else "")
        if metin != self.get():
            self.delete(0, "end")
            self.insert(0, metin)
        # imleci aynı sayıda rakamın arkasına koy
        konum = imlec_rakam + (imlec_rakam > 2) + (imlec_rakam > 4)
        if sona_nokta and imlec_rakam == len(rakam):
            konum = len(metin)
        self.icursor(min(konum, len(metin)))

    def _tus(self, e):
        if e.keysym in self.AYRACLAR:
            rakam = re.sub(r"\D", "", self.get())
            if len(rakam) in (1, 3):                  # 6. -> 06.   06.1. -> 06.01.
                rakam = rakam[:-1] + "0" + rakam[-1]
            if len(rakam) in (2, 4):
                self._yaz(rakam, len(rakam), sona_nokta=True)
            return "break"
        if e.char and e.char.isprintable() and not e.char.isdigit() and not e.state & 0x4:
            return "break"                            # harf vb. yazılmasın (Ctrl+V/C/A serbest)

    def _duzenle(self, e):
        if e.keysym in self.AYRACLAR:
            return
        metin = self.get()
        imlec = self.index("insert")
        once = len(re.sub(r"\D", "", metin[:imlec]))
        rakam = re.sub(r"\D", "", metin)[:8]
        # rakam yazılıp gün/ay tamamlandıysa noktayı hemen göster; silerken gösterme
        sona_nokta = bool(e.char and e.char.isdigit()) and len(rakam) in (2, 4) and once == len(rakam)
        self._yaz(rakam, min(once, len(rakam)), sona_nokta)


# ---------------------------------------------------------------- öneri kutusu
class OneriGiris(ttk.Entry):
    """Yazdıkça daha önce girilen kayıtlardan öneri listesi gösteren giriş kutusu.

    kaynak: öneri adaylarını döndüren fonksiyon
    secildi: bir öneri seçildiğinde çağrılır (seçilen metinle)
    """
    YOKSAY = {"Up", "Down", "Return", "KP_Enter", "Escape", "Tab", "Left", "Right", "Home",
              "End", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock"}
    EN_FAZLA = 8

    def __init__(self, ana, kaynak, secildi=None, **kw):
        super().__init__(ana, **kw)
        self.kaynak, self.secildi = kaynak, secildi
        self.ust = self.winfo_toplevel()
        self.lb = tk.Listbox(self.ust, activestyle="none", exportselection=False, takefocus=0,
                             relief="solid", borderwidth=1, selectborderwidth=0,
                             selectbackground=TURUNCU, selectforeground="white")
        self.satir_y = tkfont.nametofont(self.lb.cget("font")).metrics("linespace") + 1
        self.lb.bind("<Button-1>", self._tik)
        self.lb.bind("<Motion>", self._uzerinde)
        self.bind("<KeyRelease>", self._yaz)
        self.bind("<Down>", lambda e: self._kaydir(1))
        self.bind("<Up>", lambda e: self._kaydir(-1))
        self.bind("<Return>", self._enter)
        self.bind("<KP_Enter>", self._enter)
        self.bind("<Escape>", self._esc)
        self.bind("<FocusOut>", lambda e: self.after(150, self._odak_kontrol))
        self.ust.bind("<Button-1>", self._disari_tik, add="+")
        self.ust.bind("<Configure>", lambda e: e.widget is self.ust and self.gizle(), add="+")

    def acik(self):
        return bool(self.lb.winfo_ismapped())

    def gizle(self):
        self.lb.place_forget()

    def goster(self):
        q = kucuk(self.get().strip())
        if not q:
            self.gizle()
            return
        adaylar = list(dict.fromkeys(self.kaynak()))
        bas = [a for a in adaylar if kucuk(a).startswith(q)]
        ic = [a for a in adaylar if q in kucuk(a) and a not in bas]
        eslesen = (bas + ic)[:self.EN_FAZLA]
        if not eslesen or (len(eslesen) == 1 and kucuk(eslesen[0]) == q):
            self.gizle()
            return
        x = self.winfo_rootx() - self.ust.winfo_rootx()
        y = self.winfo_rooty() - self.ust.winfo_rooty() + self.winfo_height()
        sigan = max(2, int((self.ust.winfo_height() - y - 8) / self.satir_y))
        self.lb.delete(0, "end")
        for e in eslesen:
            self.lb.insert("end", e)
        self.lb.config(height=min(len(eslesen), sigan))
        self.lb.place(x=x, y=y, width=max(self.winfo_width(), 200))
        self.lb.lift()

    def _sec(self, deger):
        self.delete(0, "end")
        self.insert(0, deger)
        self.icursor("end")
        self.gizle()
        self.focus_set()
        if self.secildi:
            self.secildi(deger)

    def _yaz(self, e):
        if e.keysym not in self.YOKSAY:
            self.goster()

    def _kaydir(self, yon):
        if not self.acik():
            self.goster()
            return "break"
        n = self.lb.size()
        s = self.lb.curselection()
        i = (s[0] + yon) % n if s else (0 if yon > 0 else n - 1)
        self.lb.selection_clear(0, "end")
        self.lb.selection_set(i)
        self.lb.see(i)
        return "break"

    def _enter(self, _):
        if self.acik():
            s = self.lb.curselection()
            if s:
                self._sec(self.lb.get(s[0]))
                return "break"
            self.gizle()

    def _esc(self, _):
        if self.acik():
            self.gizle()
            return "break"

    def _tik(self, e):
        self._sec(self.lb.get(self.lb.nearest(e.y)))
        return "break"

    def _uzerinde(self, e):
        self.lb.selection_clear(0, "end")
        self.lb.selection_set(self.lb.nearest(e.y))

    def _disari_tik(self, e):
        if e.widget not in (self, self.lb):
            self.gizle()

    def _odak_kontrol(self):
        try:
            if self.focus_get() is not self:
                self.gizle()
        except (KeyError, tk.TclError):
            self.gizle()


# ---------------------------------------------------------------- veritabanı
class DB:
    def __init__(self, yol):
        self.con = sqlite3.connect(yol)
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS musteri (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad TEXT NOT NULL,
                telefon TEXT DEFAULT '',
                notlar TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS islem (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                musteri_id INTEGER NOT NULL REFERENCES musteri(id) ON DELETE CASCADE,
                tur TEXT NOT NULL CHECK (tur IN ('SATIŞ', 'TAHSİLAT')),
                tarih TEXT NOT NULL,
                tutar REAL NOT NULL,
                aciklama TEXT DEFAULT '',
                fis_no INTEGER
            );
            CREATE TABLE IF NOT EXISTS kalem (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                islem_id INTEGER NOT NULL REFERENCES islem(id) ON DELETE CASCADE,
                urun TEXT NOT NULL,
                adet REAL NOT NULL,
                birim_fiyat REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS gider (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tarih TEXT NOT NULL,
                kategori TEXT DEFAULT '',
                tutar REAL NOT NULL,
                aciklama TEXT DEFAULT ''
            );
        """)
        # eski veritabanı: fiş numarası sütununu ekle, mevcut satışları tarih sırasıyla numarala
        if "fis_no" not in [r[1] for r in self.con.execute("PRAGMA table_info(islem)")]:
            self.con.execute("ALTER TABLE islem ADD COLUMN fis_no INTEGER")
            satislar = self.sorgu("SELECT id FROM islem WHERE tur='SATIŞ' ORDER BY tarih, id")
            self.con.executemany("UPDATE islem SET fis_no=? WHERE id=?",
                                 [(n, i) for n, (i,) in enumerate(satislar, 1)])
        self.con.execute("CREATE UNIQUE INDEX IF NOT EXISTS islem_fis_no ON islem(fis_no) "
                         "WHERE fis_no IS NOT NULL")
        self.con.commit()
        self.yol = yol
        self._senkron_kur()

    def yedek_al(self, neden):
        """Veritabanının tarihli kopyasını Yedekler klasörüne alır; son 30 yedek saklanır."""
        klasor = os.path.join(os.path.dirname(os.path.abspath(self.yol)), "Yedekler")
        os.makedirs(klasor, exist_ok=True)
        hedef = sqlite3.connect(os.path.join(klasor, f"muhasebe_{datetime.now():%Y-%m-%d_%H-%M-%S}_{neden}.db"))
        with hedef:
            self.con.backup(hedef)
        hedef.close()
        for eski in sorted(f for f in os.listdir(klasor) if f.endswith(".db"))[:-30]:
            os.remove(os.path.join(klasor, eski))

    SEMA_SURUMU = 2

    def _senkron_kur(self):
        """Sunucuyla eşitleme için her kayda kalıcı kimlik (uuid), değişiklik zamanı ve
        'gönderilecek' işareti (kirli) ekler.

        Damgaları tetikleyiciler (trigger) basar; böylece satış, tahsilat, Excel aktarımı gibi
        her yazma işlemi ayrıca kod gerektirmeden eşitlemeye dahil olur. Eşitleme kendi
        yazdıklarını işaretlememek için senkron_kilit tablosunu 1 yapar.
        Mevcut bütün kayıtlar kirli=1 ile başlar: ilk eşitlemede yereldeki veri sunucuya yüklenir.
        """
        if self.tek("PRAGMA user_version") >= self.SEMA_SURUMU:
            return
        simdi = "CAST((julianday('now') - 2440587.5) * 86400000 AS INTEGER)"
        yeni_id = "lower(hex(randomblob(16)))"
        kilitli = "(SELECT aktif FROM senkron_kilit LIMIT 1)"
        tablolar = ("musteri", "islem", "gider")
        if self.tek("SELECT COUNT(*) FROM musteri") or self.tek("SELECT COUNT(*) FROM gider"):
            self.yedek_al("sunucu_oncesi")
        self.con.execute("""CREATE TABLE IF NOT EXISTS silinen (
                                uuid TEXT PRIMARY KEY, tablo TEXT NOT NULL, zaman INTEGER NOT NULL)""")
        for t in tablolar + ("silinen",):
            kolonlar = [r[1] for r in self.con.execute(f"PRAGMA table_info({t})")]
            if t != "silinen" and "uuid" not in kolonlar:
                self.con.execute(f"ALTER TABLE {t} ADD COLUMN uuid TEXT")
                self.con.execute(f"ALTER TABLE {t} ADD COLUMN guncelleme INTEGER")
                self.con.execute(f"UPDATE {t} SET uuid = {yeni_id}, guncelleme = {simdi}")
            if "kirli" not in kolonlar:
                self.con.execute(f"ALTER TABLE {t} ADD COLUMN kirli INTEGER NOT NULL DEFAULT 1")
        self.con.execute("CREATE TABLE IF NOT EXISTS senkron_kilit (aktif INTEGER NOT NULL)")
        if not self.tek("SELECT COUNT(*) FROM senkron_kilit"):
            self.con.execute("INSERT INTO senkron_kilit VALUES (0)")
        self.con.execute("CREATE TABLE IF NOT EXISTS ayar (anahtar TEXT PRIMARY KEY, deger TEXT)")
        for t in tablolar:
            for eski in ("damga_ekle", "damga_guncelle", "damga_sil"):
                self.con.execute(f"DROP TRIGGER IF EXISTS {t}_{eski}")
            self.con.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {t}_uuid ON {t}(uuid)")
            self.con.execute(f"""CREATE TRIGGER {t}_damga_ekle AFTER INSERT ON {t}
                                 WHEN NEW.uuid IS NULL BEGIN
                                     UPDATE {t} SET uuid = {yeni_id}, guncelleme = {simdi}, kirli = 1 WHERE id = NEW.id;
                                 END""")
            self.con.execute(f"""CREATE TRIGGER {t}_damga_guncelle AFTER UPDATE ON {t}
                                 WHEN NEW.guncelleme IS OLD.guncelleme AND NEW.uuid IS OLD.uuid AND {kilitli} = 0 BEGIN
                                     UPDATE {t} SET guncelleme = {simdi}, kirli = 1 WHERE id = NEW.id;
                                 END""")
            self.con.execute(f"""CREATE TRIGGER {t}_damga_sil AFTER DELETE ON {t} BEGIN
                                     INSERT OR REPLACE INTO silinen (uuid, tablo, zaman, kirli)
                                     VALUES (OLD.uuid, '{t}', {simdi}, CASE WHEN {kilitli} = 1 THEN 0 ELSE 1 END);
                                 END""")
        self.con.execute(f"PRAGMA user_version = {self.SEMA_SURUMU}")
        self.con.commit()

    def ayar(self, anahtar, varsayilan=""):
        r = self.con.execute("SELECT deger FROM ayar WHERE anahtar = ?", (anahtar,)).fetchone()
        return r[0] if r and r[0] is not None else varsayilan

    def ayar_yaz(self, anahtar, deger):
        self.con.execute("INSERT OR REPLACE INTO ayar (anahtar, deger) VALUES (?, ?)", (anahtar, str(deger)))
        self.con.commit()

    def bekleyen_sayisi(self):
        """Sunucuya henüz gönderilmemiş değişiklik sayısı."""
        return sum(self.tek(f"SELECT COUNT(*) FROM {t} WHERE kirli = 1") for t in ("musteri", "islem", "gider", "silinen"))

    def sorgu(self, sql, *p):
        return self.con.execute(sql, p).fetchall()

    def tek(self, sql, *p):
        return self.con.execute(sql, p).fetchone()[0]

    # --- müşteri
    def musteriler(self, ara="", yil=None):
        """[(id, ad, telefon, önceki yıldan devir, yıl içi satış, yıl içi tahsilat), ...]

        Yıl verilirse: o yıl işlemi olan, önceki yıldan borcu/alacağı devreden veya
        hiç işlemi olmayan (yeni) müşteriler listelenir. Arama yapılırsa hepsi aranır.
        """
        q = kucuk(ara)
        bas, bit = (f"{yil}-01-01", f"{yil}-12-31") if yil else ("0000-01-01", "9999-12-31")
        satirlar = self.sorgu("""
            SELECT m.id, m.ad, m.telefon,
                COALESCE(SUM(CASE WHEN i.tarih < ? THEN
                    (CASE WHEN i.tur='SATIŞ' THEN i.tutar ELSE -i.tutar END) END), 0),
                COALESCE(SUM(CASE WHEN i.tur='SATIŞ' AND i.tarih BETWEEN ? AND ? THEN i.tutar END), 0),
                COALESCE(SUM(CASE WHEN i.tur='TAHSİLAT' AND i.tarih BETWEEN ? AND ? THEN i.tutar END), 0),
                COUNT(i.id),
                COALESCE(SUM(CASE WHEN i.tarih BETWEEN ? AND ? THEN 1 END), 0)
            FROM musteri m LEFT JOIN islem i ON i.musteri_id = m.id
            GROUP BY m.id ORDER BY m.ad COLLATE NOCASE
        """, bas, bas, bit, bas, bit, bas, bit)
        return [s[:6] for s in satirlar
                if q in kucuk(s[1]) and (q or s[6] == 0 or s[7] > 0 or abs(s[3]) > 0.005)]

    def yillar(self):
        """İlk kaydın yılından bu yıla kadar (arada işlem olmayan yıllar dahil), yeniden eskiye."""
        yillar = {int(r[0]) for r in self.sorgu(
            "SELECT DISTINCT substr(tarih, 1, 4) FROM islem UNION SELECT DISTINCT substr(tarih, 1, 4) FROM gider")}
        yillar.add(date.today().year)
        return list(range(max(yillar), min(yillar) - 1, -1))

    def devir(self, mid, yil):
        """Müşterinin verilen yıla önceki yıllardan devreden bakiyesi."""
        return self.tek("""SELECT COALESCE(SUM(CASE WHEN tur='SATIŞ' THEN tutar ELSE -tutar END), 0)
                           FROM islem WHERE musteri_id=? AND tarih < ?""", mid, f"{yil}-01-01")

    def musteri(self, mid):
        return self.con.execute(
            "SELECT id, ad, telefon, notlar FROM musteri WHERE id=?", (mid,)).fetchone()

    def musteri_adlari(self):
        return [r[0] for r in self.sorgu("SELECT ad FROM musteri ORDER BY ad COLLATE NOCASE")]

    def musteri_bul(self, ad):
        """Adı (büyük/küçük harf farkı gözetmeden) birebir eşleşen müşterinin id'si."""
        ad = kucuk(ad.strip())
        for mid, a in self.sorgu("SELECT id, ad FROM musteri"):
            if kucuk(a.strip()) == ad:
                return mid
        return None

    def musteri_ekle(self, ad, telefon, notlar):
        cur = self.con.execute(
            "INSERT INTO musteri (ad, telefon, notlar) VALUES (?, ?, ?)", (ad, telefon, notlar))
        self.con.commit()
        return cur.lastrowid

    def musteri_guncelle(self, mid, ad, telefon, notlar):
        self.con.execute("UPDATE musteri SET ad=?, telefon=?, notlar=? WHERE id=?",
                         (ad, telefon, notlar, mid))
        self.con.commit()

    def musteri_sil(self, mid):
        self.con.execute("DELETE FROM musteri WHERE id=?", (mid,))
        self.con.commit()

    # --- satış / tahsilat
    def islemler(self, mid, yil=None):
        bas, bit = (f"{yil}-01-01", f"{yil}-12-31") if yil else ("0000-01-01", "9999-12-31")
        return self.sorgu("""
            SELECT id, tur, tarih, tutar, aciklama, fis_no FROM islem
            WHERE musteri_id=? AND tarih BETWEEN ? AND ? ORDER BY tarih, id
        """, mid, bas, bit)

    def son_islemler(self, adet=300, mid=None):
        """Girilme sırasına göre son işlemler (en yeni önce), fişlerin her ürünü ayrı satır:
        [(islem_id, fis_no, tarih, müşteri, tür, ürün, adet, birim_fiyat, işlem_tutarı, açıklama, musteri_id)]"""
        filtre, p = ("WHERE musteri_id = ?", (mid, adet)) if mid else ("", (adet,))
        return self.sorgu(f"""
            SELECT i.id, i.fis_no, i.tarih, m.ad, i.tur, k.urun, k.adet, k.birim_fiyat, i.tutar,
                   i.aciklama, i.musteri_id
            FROM islem i JOIN musteri m ON m.id = i.musteri_id
                 LEFT JOIN kalem k ON k.islem_id = i.id
            WHERE i.id IN (SELECT id FROM islem {filtre} ORDER BY id DESC LIMIT ?)
            ORDER BY i.id DESC, k.id
        """, *p)

    def sonraki_fis_no(self):
        return self.tek("SELECT COALESCE(MAX(fis_no), 0) + 1 FROM islem")

    def fis_kullanan(self, fis_no, haric=None):
        """Bu fiş numarası başka bir satışta kullanılıyorsa (müşteri adı, tarih)."""
        return self.con.execute("""
            SELECT m.ad, i.tarih FROM islem i JOIN musteri m ON m.id = i.musteri_id
            WHERE i.fis_no = ? AND i.id IS NOT ?""", (fis_no, haric)).fetchone()

    def satis(self, iid):
        return self.con.execute(
            "SELECT musteri_id, tarih, aciklama, fis_no FROM islem WHERE id=?", (iid,)).fetchone()

    def tahsilat(self, iid):
        return self.con.execute(
            "SELECT tarih, tutar, aciklama FROM islem WHERE id=?", (iid,)).fetchone()

    def kalemler(self, iid):
        return self.sorgu(
            "SELECT urun, adet, birim_fiyat FROM kalem WHERE islem_id=? ORDER BY id", iid)

    def urun_adlari(self):
        """Daha önce satılan ürünler, en çok satılandan başlayarak."""
        return [r[0] for r in self.sorgu(
            "SELECT urun FROM kalem GROUP BY urun ORDER BY COUNT(*) DESC, urun")]

    def son_fiyat(self, urun):
        r = self.con.execute("""
            SELECT k.birim_fiyat FROM kalem k JOIN islem i ON i.id = k.islem_id
            WHERE k.urun = ? ORDER BY i.tarih DESC, k.id DESC LIMIT 1
        """, (urun,)).fetchone()
        return r[0] if r else None

    def satis_ekle(self, mid, tarih, kalemler, aciklama, fis_no=None):
        toplam = round(sum(a * f for _, a, f in kalemler), 2)
        with self.con:
            cur = self.con.execute(
                "INSERT INTO islem (musteri_id, tur, tarih, tutar, aciklama, fis_no) "
                "VALUES (?, 'SATIŞ', ?, ?, ?, ?)",
                (mid, tarih, toplam, aciklama, fis_no or self.sonraki_fis_no()))
            self.con.executemany(
                "INSERT INTO kalem (islem_id, urun, adet, birim_fiyat) VALUES (?, ?, ?, ?)",
                [(cur.lastrowid, u, a, f) for u, a, f in kalemler])
        return cur.lastrowid

    def satis_guncelle(self, iid, mid, tarih, kalemler, aciklama, fis_no):
        toplam = round(sum(a * f for _, a, f in kalemler), 2)
        with self.con:
            self.con.execute("""UPDATE islem SET musteri_id=?, tarih=?, tutar=?, aciklama=?, fis_no=?
                                WHERE id=?""", (mid, tarih, toplam, aciklama, fis_no, iid))
            self.con.execute("DELETE FROM kalem WHERE islem_id=?", (iid,))
            self.con.executemany(
                "INSERT INTO kalem (islem_id, urun, adet, birim_fiyat) VALUES (?, ?, ?, ?)",
                [(iid, u, a, f) for u, a, f in kalemler])

    def tahsilat_ekle(self, mid, tarih, tutar, aciklama):
        self.con.execute(
            "INSERT INTO islem (musteri_id, tur, tarih, tutar, aciklama) VALUES (?, 'TAHSİLAT', ?, ?, ?)",
            (mid, tarih, tutar, aciklama))
        self.con.commit()

    def tahsilat_guncelle(self, iid, tarih, tutar, aciklama):
        self.con.execute("UPDATE islem SET tarih=?, tutar=?, aciklama=? WHERE id=?",
                         (tarih, tutar, aciklama, iid))
        self.con.commit()

    def islem_sil(self, iid):
        self.con.execute("DELETE FROM islem WHERE id=?", (iid,))
        self.con.commit()

    # --- gider
    def gider_ekle(self, tarih, kategori, tutar, aciklama):
        self.con.execute("INSERT INTO gider (tarih, kategori, tutar, aciklama) VALUES (?, ?, ?, ?)",
                         (tarih, kategori, tutar, aciklama))
        self.con.commit()

    def gider_sil(self, gid):
        self.con.execute("DELETE FROM gider WHERE id=?", (gid,))
        self.con.commit()

    def giderler(self, bas, bit):
        return self.sorgu("""
            SELECT id, tarih, kategori, tutar, aciklama FROM gider
            WHERE tarih BETWEEN ? AND ? ORDER BY tarih, id
        """, bas, bit)

    def gider_kategorileri(self):
        kayitli = [r[0] for r in self.sorgu(
            "SELECT kategori FROM gider WHERE kategori <> '' GROUP BY kategori ORDER BY COUNT(*) DESC")]
        return kayitli + [k for k in VARSAYILAN_GIDERLER if k not in kayitli]

    # --- raporlar
    def ilk_tarih(self):
        return self.tek("""SELECT MIN(t) FROM (SELECT MIN(tarih) t FROM islem
                                              UNION ALL SELECT MIN(tarih) FROM gider)""")

    def ozet(self, bas, bit):
        sayi, ciro = self.con.execute("""
            SELECT COUNT(*), COALESCE(SUM(tutar), 0) FROM islem
            WHERE tur='SATIŞ' AND tarih BETWEEN ? AND ?""", (bas, bit)).fetchone()
        return {
            "satis_sayisi": sayi,
            "ciro": ciro,
            "tahsilat": self.tek("""SELECT COALESCE(SUM(tutar), 0) FROM islem
                                    WHERE tur='TAHSİLAT' AND tarih BETWEEN ? AND ?""", bas, bit),
            "gider": self.tek("SELECT COALESCE(SUM(tutar), 0) FROM gider WHERE tarih BETWEEN ? AND ?",
                              bas, bit),
            "urun_adedi": self.tek("""SELECT COALESCE(SUM(k.adet), 0) FROM kalem k
                                      JOIN islem i ON i.id = k.islem_id
                                      WHERE i.tarih BETWEEN ? AND ?""", bas, bit),
            "alacak": self.tek("""SELECT COALESCE(SUM(CASE WHEN tur='SATIŞ' THEN tutar ELSE -tutar END), 0)
                                  FROM islem WHERE tarih <= ?""", bit),
        }

    def donem_dokumu(self, bas, bit, aylik):
        """[(dönem, satış, tahsilat, gider), ...] gün veya ay bazında."""
        anahtar = "substr(tarih, 1, 7)" if aylik else "tarih"
        veri = {}
        for k, tur, t in self.sorgu(f"""SELECT {anahtar}, tur, SUM(tutar) FROM islem
                                       WHERE tarih BETWEEN ? AND ? GROUP BY 1, 2""", bas, bit):
            veri.setdefault(k, [0, 0, 0])[0 if tur == "SATIŞ" else 1] += t
        for k, t in self.sorgu(f"""SELECT {anahtar}, SUM(tutar) FROM gider
                                  WHERE tarih BETWEEN ? AND ? GROUP BY 1""", bas, bit):
            veri.setdefault(k, [0, 0, 0])[2] += t
        return [(k, *v) for k, v in sorted(veri.items())]

    def urun_raporu(self, bas, bit):
        return self.sorgu("""
            SELECT k.urun, SUM(k.adet), COUNT(DISTINCT k.islem_id), SUM(k.adet * k.birim_fiyat)
            FROM kalem k JOIN islem i ON i.id = k.islem_id
            WHERE i.tarih BETWEEN ? AND ?
            GROUP BY k.urun ORDER BY 4 DESC
        """, bas, bit)

    def musteri_raporu(self, bas, bit):
        satirlar = self.sorgu("""
            SELECT m.id, m.ad,
                SUM(CASE WHEN i.tur='SATIŞ' AND i.tarih BETWEEN ? AND ? THEN i.tutar ELSE 0 END),
                SUM(CASE WHEN i.tur='TAHSİLAT' AND i.tarih BETWEEN ? AND ? THEN i.tutar ELSE 0 END),
                SUM(CASE WHEN i.tarih <= ? THEN
                    (CASE WHEN i.tur='SATIŞ' THEN i.tutar ELSE -i.tutar END) ELSE 0 END)
            FROM musteri m JOIN islem i ON i.musteri_id = m.id
            GROUP BY m.id ORDER BY 3 DESC, 4 DESC
        """, bas, bit, bas, bit, bit)
        return [s for s in satirlar if s[2] or s[3]]


# ---------------------------------------------------------------- pencereler
class MusteriPenceresi(tk.Toplevel):
    def __init__(self, ana, db, mid=None, kaydedildi=None):
        super().__init__(ana)
        self.db, self.mid, self.kaydedildi = db, mid, kaydedildi
        self.title("Müşteri Düzenle" if mid else "Yeni Müşteri")
        self.geometry("400x230")
        self.resizable(False, False)
        self.transient(ana)
        self.grab_set()

        f = ttk.Frame(self, padding=12)
        f.pack(fill="both", expand=True)
        self.ad, self.tel, self.notlar = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(f, text="Ad Soyad / Firma *").grid(row=0, column=0, sticky="w", pady=3)
        ad_giris = OneriGiris(f, db.musteri_adlari, textvariable=self.ad, width=34)
        ad_giris.grid(row=0, column=1, pady=3, padx=(8, 0))
        for r, (etiket, var) in enumerate([("Telefon", self.tel), ("Not", self.notlar)], start=1):
            ttk.Label(f, text=etiket).grid(row=r, column=0, sticky="w", pady=3)
            ttk.Entry(f, textvariable=var, width=34).grid(row=r, column=1, pady=3, padx=(8, 0))
        if mid:
            _, ad, tel, notlar = db.musteri(mid)
            self.ad.set(ad); self.tel.set(tel); self.notlar.set(notlar)
        ttk.Button(f, text="Kaydet", command=self.kaydet).grid(row=3, column=1, sticky="e", pady=(10, 0))
        self.bind("<Return>", lambda e: self.kaydet())
        ad_giris.focus_set()

    def kaydet(self):
        ad = self.ad.get().strip()
        if not ad:
            messagebox.showwarning("Eksik", "Ad boş olamaz.", parent=self)
            return
        ayni = self.db.musteri_bul(ad)
        if ayni and ayni != self.mid and not messagebox.askyesno(
                "Aynı isim", f"'{ad}' adlı bir müşteri zaten var. Yine de kaydedilsin mi?", parent=self):
            return
        if self.mid:
            self.db.musteri_guncelle(self.mid, ad, self.tel.get().strip(), self.notlar.get().strip())
            mid = self.mid
        else:
            mid = self.db.musteri_ekle(ad, self.tel.get().strip(), self.notlar.get().strip())
        self.destroy()
        if self.kaydedildi:
            self.kaydedildi(mid)


class SatisPenceresi(tk.Toplevel):
    def __init__(self, ana, db, mid, kaydedildi, iid=None):
        """iid verilirse mevcut fiş düzenlenir."""
        super().__init__(ana)
        self.db, self.kaydedildi, self.iid = db, kaydedildi, iid
        self.kalemler, self.duzenlenen = [], None
        aciklama = ""
        if iid:
            mid, tarih, aciklama, fis_no = db.satis(iid)
            self.kalemler = list(db.kalemler(iid))
        else:
            tarih, fis_no = date.today().isoformat(), db.sonraki_fis_no()
        self.title(f"Fiş Düzenle - Fiş No {fis_no}" if iid else "Yeni Satış")
        self.geometry("780x560")
        self.transient(ana)
        self.grab_set()

        ust = ttk.Frame(self, padding=10)
        ust.pack(fill="x")
        ttk.Label(ust, text="Müşteri:").pack(side="left")
        self.musteri = tk.StringVar(value=db.musteri(mid)[1] if mid else "")
        self.musteri_giris = OneriGiris(ust, db.musteri_adlari, textvariable=self.musteri, width=32,
                                        secildi=lambda _: self.urun_giris.focus_set())
        self.musteri_giris.pack(side="left", padx=6)
        self.tarih = tk.StringVar(value=tarih_goster(tarih))
        TarihGiris(ust, textvariable=self.tarih, width=12).pack(side="right")
        ttk.Label(ust, text="Tarih (GG.AA.YYYY):").pack(side="right", padx=(12, 4))
        self.fis = tk.StringVar(value=str(fis_no))
        ttk.Entry(ust, textvariable=self.fis, width=7).pack(side="right")
        ttk.Label(ust, text="Fiş No:").pack(side="right", padx=4)

        giris = ttk.LabelFrame(self, text="Ürün Ekle  (listedeki bir satırı düzeltmek için üzerine çift tıklayın)",
                               padding=10)
        giris.pack(fill="x", padx=10)
        self.urun, self.adet, self.fiyat = tk.StringVar(), tk.StringVar(value="1"), tk.StringVar()
        ttk.Label(giris, text="Ürün Adı").grid(row=0, column=0, sticky="w")
        ttk.Label(giris, text="Adet").grid(row=0, column=1, sticky="w")
        ttk.Label(giris, text="Birim Fiyat").grid(row=0, column=2, sticky="w")
        self.urun_giris = OneriGiris(giris, db.urun_adlari, self.urun_secildi,
                                     textvariable=self.urun, width=32)
        self.urun_giris.grid(row=1, column=0, padx=(0, 6))
        self.adet_giris = ttk.Entry(giris, textvariable=self.adet, width=8)
        self.adet_giris.grid(row=1, column=1, padx=(0, 6))
        ttk.Entry(giris, textvariable=self.fiyat, width=12).grid(row=1, column=2, padx=(0, 6))
        self.ekle_btn = ttk.Button(giris, text="Ekle", command=self.kalem_ekle)
        self.ekle_btn.grid(row=1, column=3)
        for w in giris.winfo_children():
            if isinstance(w, ttk.Entry):
                w.bind("<Return>", lambda e: self.kalem_ekle(), add="+")

        kap, self.tv = tablo(self, [("urun", "Ürün", 260, "w"), ("adet", "Adet", 70, "e"),
                                    ("fiyat", "Birim Fiyat", 110, "e"), ("tutar", "Tutar", 120, "e")])
        kap.pack(fill="both", expand=True, padx=10, pady=8)
        self.tv.bind("<Delete>", lambda e: self.kalem_sil())
        self.tv.bind("<Double-1>", self.kalem_duzenle)

        alt = ttk.Frame(self, padding=10)
        alt.pack(fill="x")
        ttk.Button(alt, text="Seçili Satırı Sil", command=self.kalem_sil).pack(side="left")
        ttk.Label(alt, text="Açıklama:").pack(side="left", padx=(12, 4))
        self.aciklama = tk.StringVar(value=aciklama)
        ttk.Entry(alt, textvariable=self.aciklama, width=22).pack(side="left")
        ttk.Button(alt, text="DEĞİŞİKLİKLERİ KAYDET" if iid else "SATIŞI KAYDET", style="Vurgu.TButton",
                   command=self.kaydet).pack(side="right")
        self.toplam_lbl = ttk.Label(alt, text="Toplam: " + para(0), font=("Segoe UI", 11, "bold"))
        self.toplam_lbl.pack(side="right", padx=12)
        self.yenile()
        (self.urun_giris if mid else self.musteri_giris).focus_set()

    def kalem_duzenle(self, e):
        satir = self.tv.identify_row(e.y)
        if not satir:
            return
        self.duzenlenen = int(satir)
        urun, adet, fiyat = self.kalemler[self.duzenlenen]
        self.urun.set(urun)
        self.adet.set(f"{adet:g}".replace(".", ","))
        self.fiyat.set(f"{fiyat:.2f}".replace(".", ","))
        self.ekle_btn.config(text="Güncelle")
        self.adet_giris.focus_set()
        self.adet_giris.select_range(0, "end")

    def urun_secildi(self, urun):
        """Önerilen ürün seçilince son satış fiyatını getir, adete geç."""
        fiyat = self.db.son_fiyat(urun)
        if fiyat is not None and not self.fiyat.get().strip():
            self.fiyat.set(f"{fiyat:.2f}".replace(".", ","))
        self.adet_giris.focus_set()
        self.adet_giris.select_range(0, "end")

    def yenile(self):
        self.tv.delete(*self.tv.get_children())
        for i, (u, a, f) in enumerate(self.kalemler):
            self.tv.insert("", "end", iid=str(i), values=(u, f"{a:g}", para(f), para(a * f)))
        self.toplam_lbl.config(text="Toplam: " + para(sum(a * f for _, a, f in self.kalemler)))

    def kalem_ekle(self):
        urun = self.urun.get().strip()
        try:
            adet, fiyat = sayi_oku(self.adet.get()), sayi_oku(self.fiyat.get())
        except ValueError:
            messagebox.showwarning("Hatalı giriş", "Adet ve birim fiyat sayı olmalı.", parent=self)
            return
        if not urun or adet <= 0 or (fiyat < 0 and "indirim" not in kucuk(urun)):
            messagebox.showwarning("Hatalı giriş", "Ürün adı, pozitif adet ve fiyat girin.", parent=self)
            return
        if self.duzenlenen is not None:
            self.kalemler[self.duzenlenen] = (urun, adet, fiyat)
        else:
            self.kalemler.append((urun, adet, fiyat))
        self.duzenleme_bitir()
        self.urun.set(""); self.adet.set("1"); self.fiyat.set("")
        self.yenile()
        self.urun_giris.focus_set()

    def duzenleme_bitir(self):
        self.duzenlenen = None
        self.ekle_btn.config(text="Ekle")

    def kalem_sil(self):
        for iid in sorted((int(i) for i in self.tv.selection()), reverse=True):
            del self.kalemler[iid]
        self.duzenleme_bitir()
        self.yenile()

    def kaydet(self):
        ad = self.musteri.get().strip()
        if not ad:
            messagebox.showwarning("Eksik", "Müşteri adını girin.", parent=self)
            return
        if not self.kalemler:
            messagebox.showwarning("Boş", "En az bir ürün ekleyin.", parent=self)
            return
        try:
            tarih = tarih_oku(self.tarih.get())
        except ValueError:
            messagebox.showwarning("Hatalı tarih", "Tarihi GG.AA.YYYY biçiminde girin.", parent=self)
            return
        try:
            fis_no = int(self.fis.get().strip())
            if fis_no <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Hatalı fiş no", "Fiş numarası pozitif bir tam sayı olmalı.", parent=self)
            return
        kullanan = self.db.fis_kullanan(fis_no, self.iid)
        if kullanan:
            messagebox.showwarning(
                "Fiş no kullanılıyor",
                f"{fis_no} numaralı fiş zaten var ({kullanan[0]}, {tarih_goster(kullanan[1])}).\n"
                f"Boştaki ilk numara: {self.db.sonraki_fis_no()}", parent=self)
            return
        mid = self.db.musteri_bul(ad)
        if mid is None:                       # kayıtlı değilse otomatik oluştur
            mid = self.db.musteri_ekle(ad, "", "")
        if self.iid:
            self.db.satis_guncelle(self.iid, mid, tarih, self.kalemler, self.aciklama.get().strip(), fis_no)
        else:
            self.db.satis_ekle(mid, tarih, self.kalemler, self.aciklama.get().strip(), fis_no)
        self.destroy()
        self.kaydedildi(mid, tarih)


class TahsilatPenceresi(tk.Toplevel):
    def __init__(self, ana, db, mid, kaydedildi, iid=None):
        """iid verilirse mevcut tahsilat düzenlenir."""
        super().__init__(ana)
        self.db, self.mid, self.kaydedildi, self.iid = db, mid, kaydedildi, iid
        self.title(f"{'Tahsilat Düzenle' if iid else 'Tahsilat (Ödeme Al)'} - {db.musteri(mid)[1]}")
        self.resizable(False, False)
        self.transient(ana)
        self.grab_set()

        f = ttk.Frame(self, padding=12)
        f.pack()
        tarih, tutar, aciklama = db.tahsilat(iid) if iid else (date.today().isoformat(), None, "")
        self.tarih = tk.StringVar(value=tarih_goster(tarih))
        self.tutar = tk.StringVar(value=f"{tutar:.2f}".replace(".", ",") if tutar else "")
        self.aciklama = tk.StringVar(value=aciklama)
        for r, (etiket, var) in enumerate([("Tarih (GG.AA.YYYY)", self.tarih),
                                           ("Tutar", self.tutar), ("Açıklama", self.aciklama)]):
            ttk.Label(f, text=etiket).grid(row=r, column=0, sticky="w", pady=3)
            e = (TarihGiris if var is self.tarih else ttk.Entry)(f, textvariable=var, width=28)
            e.grid(row=r, column=1, pady=3, padx=(8, 0))
            if var is self.tutar:
                e.focus_set()
        ttk.Button(f, text="Kaydet", command=self.kaydet).grid(row=3, column=1, sticky="e", pady=(10, 0))
        self.bind("<Return>", lambda e: self.kaydet())

    def kaydet(self):
        try:
            tarih = tarih_oku(self.tarih.get())
            tutar = sayi_oku(self.tutar.get())
        except ValueError:
            messagebox.showwarning("Hatalı giriş", "Tarih GG.AA.YYYY, tutar sayı olmalı.", parent=self)
            return
        if tutar <= 0:
            messagebox.showwarning("Hatalı giriş", "Tutar sıfırdan büyük olmalı.", parent=self)
            return
        if self.iid:
            self.db.tahsilat_guncelle(self.iid, tarih, tutar, self.aciklama.get().strip())
        else:
            self.db.tahsilat_ekle(self.mid, tarih, tutar, self.aciklama.get().strip())
        self.destroy()
        self.kaydedildi()


class BilancoPenceresi(tk.Toplevel):
    """Seçilen tarih aralığı için gelir/gider, satış ve müşteri istatistikleri."""
    GRAFIK_RENK = (("Satış", TURUNCU), ("Tahsilat", YESIL), ("Gider", KIRMIZI))

    def __init__(self, ana, db, musteri_ac):
        super().__init__(ana)
        self.db, self.musteri_ac = db, musteri_ac
        self.title("Bilanço / Raporlar")
        self.geometry("1050x720")
        self.minsize(850, 560)
        self.grafik_veri = []

        # --- tarih aralığı
        ust = ttk.Frame(self, padding=10)
        ust.pack(fill="x")
        self.bas, self.bit = tk.StringVar(), tk.StringVar()
        ttk.Label(ust, text="Başlangıç:").pack(side="left")
        TarihGiris(ust, textvariable=self.bas, width=11).pack(side="left", padx=(4, 10))
        ttk.Label(ust, text="Bitiş:").pack(side="left")
        TarihGiris(ust, textvariable=self.bit, width=11).pack(side="left", padx=4)
        ttk.Button(ust, text="Göster", command=self.yenile).pack(side="left", padx=(4, 16))
        for ad, kod in [("Bugün", "gun"), ("Bu Hafta", "hafta"), ("Bu Ay", "ay"),
                        ("Geçen Ay", "gecen_ay"), ("Çalışma Yılı", "yil"), ("Tümü", "tumu")]:
            ttk.Button(ust, text=ad, command=lambda k=kod: self.aralik(k)).pack(side="left", padx=2)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # --- özet sekmesi
        ozet = ttk.Frame(nb, padding=10)
        nb.add(ozet, text="  Özet  ")
        kartlar = ttk.Frame(ozet)
        kartlar.pack(fill="x")
        self.kart = {}
        for i, ad in enumerate(["Toplam Satış (Ciro)", "Satış İşlemi Sayısı", "Satılan Ürün Adedi",
                                "Tahsilat (Kasa Girişi)", "Gider (Kasa Çıkışı)", "Net Kasa (Tahsilat − Gider)",
                                "Dönem Sonucu (Satış − Gider)", "Ortalama Satış Tutarı",
                                "Toplam Alacak (Bitiş Tarihinde)"]):
            kutu = ttk.LabelFrame(kartlar, text=ad, padding=(10, 4))
            kutu.grid(row=i // 3, column=i % 3, sticky="ew", padx=4, pady=4)
            self.kart[ad] = ttk.Label(kutu, text="-", style="Bakiye.TLabel", anchor="e")
            self.kart[ad].pack(fill="x")
        for c in range(3):
            kartlar.columnconfigure(c, weight=1)

        self.grafik = tk.Canvas(ozet, height=220, background="white", highlightthickness=1,
                                highlightbackground="#cccccc")
        self.grafik.pack(fill="x", pady=(10, 6))
        self.grafik.bind("<Configure>", self.ciz)
        kap, self.dokum = tablo(ozet, [("donem", "Dönem", 120, "w"), ("satis", "Satış", 130, "e"),
                                       ("tahsilat", "Tahsilat", 130, "e"), ("gider", "Gider", 130, "e"),
                                       ("net", "Net Kasa", 130, "e")])
        kap.pack(fill="both", expand=True)
        self.dokum.tag_configure("eksi", foreground=KIRMIZI)

        # --- ürünler sekmesi
        sekme = ttk.Frame(nb, padding=10)
        nb.add(sekme, text="  Ürün Satışları  ")
        kap, self.urunler = tablo(sekme, [("sira", "#", 40, "e"), ("urun", "Ürün", 280, "w"),
                                          ("adet", "Satılan Adet", 110, "e"),
                                          ("islem", "Satış Sayısı", 100, "e"),
                                          ("ort", "Ort. Birim Fiyat", 130, "e"),
                                          ("ciro", "Toplam Tutar", 140, "e"),
                                          ("pay", "Ciro Payı", 80, "e")])
        kap.pack(fill="both", expand=True)

        # --- müşteriler sekmesi
        sekme = ttk.Frame(nb, padding=10)
        nb.add(sekme, text="  Müşteriler  ")
        ttk.Label(sekme, text="Seçilen aralıkta işlem yapan müşteriler. "
                              "Çift tıklayınca müşterinin hesabı açılır.").pack(anchor="w", pady=(0, 4))
        kap, self.musteriler = tablo(sekme, [("ad", "Müşteri", 280, "w"), ("satis", "Satış", 140, "e"),
                                             ("tahsilat", "Tahsilat", 140, "e"),
                                             ("bakiye", "Güncel Borç (Bitiş)", 160, "e")])
        kap.pack(fill="both", expand=True)
        self.musteriler.tag_configure("borclu", foreground=KIRMIZI)
        self.musteriler.bind("<Double-1>", self.musteri_cift_tik)

        # --- giderler sekmesi
        sekme = ttk.Frame(nb, padding=10)
        nb.add(sekme, text="  Giderler  ")
        form = ttk.LabelFrame(sekme, text="Gider Ekle", padding=10)
        form.pack(fill="x")
        self.g_tarih = tk.StringVar(value=date.today().strftime("%d.%m.%Y"))
        self.g_kat, self.g_tutar, self.g_acik = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for c, ad in enumerate(["Tarih", "Kategori", "Tutar", "Açıklama"]):
            ttk.Label(form, text=ad).grid(row=0, column=c, sticky="w")
        TarihGiris(form, textvariable=self.g_tarih, width=12).grid(row=1, column=0, padx=(0, 6))
        OneriGiris(form, db.gider_kategorileri, textvariable=self.g_kat, width=22).grid(
            row=1, column=1, padx=(0, 6))
        ttk.Entry(form, textvariable=self.g_tutar, width=12).grid(row=1, column=2, padx=(0, 6))
        ttk.Entry(form, textvariable=self.g_acik, width=34).grid(row=1, column=3, padx=(0, 6))
        ttk.Button(form, text="Ekle", command=self.gider_ekle).grid(row=1, column=4)
        for w in form.winfo_children():
            if isinstance(w, ttk.Entry):
                w.bind("<Return>", lambda e: self.gider_ekle(), add="+")

        kap, self.gider_tv = tablo(sekme, [("tarih", "Tarih", 90, "w"), ("kat", "Kategori", 160, "w"),
                                           ("acik", "Açıklama", 340, "w"), ("tutar", "Tutar", 130, "e")])
        kap.pack(fill="both", expand=True, pady=(10, 4))
        alt = ttk.Frame(sekme)
        alt.pack(fill="x")
        ttk.Button(alt, text="Seçili Gideri Sil", command=self.gider_sil).pack(side="left")
        self.kat_lbl = ttk.Label(alt, text="", wraplength=800, justify="left")
        self.kat_lbl.pack(side="left", padx=12)

        self.aralik("ay")

    # --- tarih aralığı
    def aralik(self, kod):
        bugun = date.today()
        bit = bugun
        if kod == "gun":
            bas = bugun
        elif kod == "hafta":
            bas = bugun - timedelta(days=bugun.weekday())
        elif kod == "ay":
            bas = bugun.replace(day=1)
        elif kod == "gecen_ay":
            bit = bugun.replace(day=1) - timedelta(days=1)
            bas = bit.replace(day=1)
        elif kod == "yil":                    # ana pencerede seçili çalışma yılı
            yil = getattr(self.master, "yil", bugun.year)
            bas, bit = date(yil, 1, 1), date(yil, 12, 31)
        else:
            ilk = self.db.ilk_tarih()
            bas = date.fromisoformat(ilk) if ilk else bugun
            bit = max(bugun, date.fromisoformat(self.db.tek(
                "SELECT COALESCE(MAX(tarih), ?) FROM islem", bugun.isoformat())))
        self.bas.set(bas.strftime("%d.%m.%Y"))
        self.bit.set(bit.strftime("%d.%m.%Y"))
        self.yenile()

    def yenile(self):
        try:
            bas, bit = tarih_oku(self.bas.get()), tarih_oku(self.bit.get())
        except ValueError:
            messagebox.showwarning("Hatalı tarih", "Tarihleri GG.AA.YYYY biçiminde girin.", parent=self)
            return
        if bas > bit:
            messagebox.showwarning("Hatalı aralık", "Başlangıç, bitişten sonra olamaz.", parent=self)
            return

        # özet kartları
        o = self.db.ozet(bas, bit)
        net, sonuc = o["tahsilat"] - o["gider"], o["ciro"] - o["gider"]
        degerler = {
            "Toplam Satış (Ciro)": (para(o["ciro"]), None),
            "Satış İşlemi Sayısı": (str(o["satis_sayisi"]), None),
            "Satılan Ürün Adedi": (f"{o['urun_adedi']:g}", None),
            "Tahsilat (Kasa Girişi)": (para(o["tahsilat"]), YESIL),
            "Gider (Kasa Çıkışı)": (para(o["gider"]), KIRMIZI),
            "Net Kasa (Tahsilat − Gider)": (para(net), YESIL if net >= 0 else KIRMIZI),
            "Dönem Sonucu (Satış − Gider)": (para(sonuc), YESIL if sonuc >= 0 else KIRMIZI),
            "Ortalama Satış Tutarı": (para(o["ciro"] / o["satis_sayisi"]) if o["satis_sayisi"] else "-", None),
            "Toplam Alacak (Bitiş Tarihinde)": (para(o["alacak"]), KIRMIZI if o["alacak"] > 0.005 else None),
        }
        for ad, (metin, renk) in degerler.items():
            self.kart[ad].config(text=metin, foreground=renk or "")

        # dönem dökümü + grafik (62 günden uzun aralıklar ay bazında)
        aylik = (date.fromisoformat(bit) - date.fromisoformat(bas)).days > 62
        self.dokum.heading("donem", text="Ay" if aylik else "Gün")
        self.dokum.delete(*self.dokum.get_children())
        self.grafik_veri = []
        for k, satis, tahsilat, gider in self.db.donem_dokumu(bas, bit, aylik):
            etiket = f"{k[5:7]}.{k[:4]}" if aylik else tarih_goster(k)
            self.grafik_veri.append((etiket if aylik else etiket[:5], satis, tahsilat, gider))
            self.dokum.insert("", "end", values=(etiket, para(satis), para(tahsilat), para(gider),
                                                 para(tahsilat - gider)),
                              tags=("eksi",) if tahsilat - gider < 0 else ())
        self.ciz()

        # ürünler
        self.urunler.delete(*self.urunler.get_children())
        for i, (urun, adet, islem, ciro) in enumerate(self.db.urun_raporu(bas, bit), 1):
            pay = f"%{ciro / o['ciro'] * 100:.1f}".replace(".", ",") if o["ciro"] else "-"
            self.urunler.insert("", "end", values=(i, urun, f"{adet:g}", islem,
                                                   para(ciro / adet if adet else 0), para(ciro), pay))

        # müşteriler
        self.musteriler.delete(*self.musteriler.get_children())
        for mid, ad, satis, tahsilat, bakiye in self.db.musteri_raporu(bas, bit):
            self.musteriler.insert("", "end", iid=str(mid),
                                   values=(ad, para(satis), para(tahsilat), para(bakiye)),
                                   tags=("borclu",) if bakiye > 0.005 else ())

        # giderler
        self.gider_tv.delete(*self.gider_tv.get_children())
        kategoriler = {}
        for gid, tarih, kat, tutar, acik in self.db.giderler(bas, bit):
            self.gider_tv.insert("", "end", iid=str(gid),
                                 values=(tarih_goster(tarih), kat, acik, para(tutar)))
            kategoriler[kat or "Diğer"] = kategoriler.get(kat or "Diğer", 0) + tutar
        self.kat_lbl.config(text="Kategori toplamları:  " + "   |   ".join(
            f"{k}: {para(v)}" for k, v in sorted(kategoriler.items(), key=lambda x: -x[1]))
            if kategoriler else "")

    def ciz(self, _=None):
        c = self.grafik
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 100:
            return
        if not self.grafik_veri:
            c.create_text(W / 2, H / 2, text="Bu aralıkta kayıt yok", fill="#888888")
            return
        sol, sag, ust, alt = 64, 12, 30, 22
        en = max(max(v[1:]) for v in self.grafik_veri) or 1
        alan_h = H - ust - alt
        for i in range(5):
            y = H - alt - alan_h * i / 4
            c.create_line(sol, y, W - sag, y, fill="#e6e6e6")
            c.create_text(sol - 6, y, text=kisa(en * i / 4), anchor="e", fill="#666666",
                          font=("Segoe UI", 8))
        n = len(self.grafik_veri)
        grup = (W - sol - sag) / n
        cubuk = max(2, min(grup * 0.8 / 3, 26))
        adim = max(1, math.ceil(n * 48 / (W - sol - sag)))
        for j, (etiket, *degerler) in enumerate(self.grafik_veri):
            x0 = sol + j * grup + (grup - 3 * cubuk) / 2
            for k, (v, (_, renk)) in enumerate(zip(degerler, self.GRAFIK_RENK)):
                if v > 0:
                    c.create_rectangle(x0 + k * cubuk, H - alt - alan_h * v / en,
                                       x0 + (k + 1) * cubuk - 1, H - alt, fill=renk, outline="")
            if j % adim == 0:
                c.create_text(sol + j * grup + grup / 2, H - alt + 3, text=etiket, anchor="n",
                              fill="#444444", font=("Segoe UI", 8))
        x = sol
        for ad, renk in self.GRAFIK_RENK:
            c.create_rectangle(x, 10, x + 12, 22, fill=renk, outline="")
            c.create_text(x + 16, 16, text=ad, anchor="w", font=("Segoe UI", 9))
            x += 90

    # --- gider işlemleri
    def gider_ekle(self):
        try:
            tarih = tarih_oku(self.g_tarih.get())
            tutar = sayi_oku(self.g_tutar.get())
        except ValueError:
            messagebox.showwarning("Hatalı giriş", "Tarih GG.AA.YYYY, tutar sayı olmalı.", parent=self)
            return
        if tutar <= 0:
            messagebox.showwarning("Hatalı giriş", "Tutar sıfırdan büyük olmalı.", parent=self)
            return
        self.db.gider_ekle(tarih, self.g_kat.get().strip(), tutar, self.g_acik.get().strip())
        self.g_kat.set(""); self.g_tutar.set(""); self.g_acik.set("")
        self.yenile()

    def gider_sil(self):
        s = self.gider_tv.selection()
        if not s:
            messagebox.showinfo("Gider Sil", "Listeden silinecek gideri seçin.", parent=self)
            return
        if messagebox.askyesno("Gider Sil", "Seçili gider silinsin mi?", parent=self):
            self.db.gider_sil(int(s[0]))
            self.yenile()

    def musteri_cift_tik(self, _):
        s = self.musteriler.selection()
        if s:
            self.musteri_ac(int(s[0]))


# ---------------------------------------------------------------- müşteri hesabı paneli
class MusteriDetay(ttk.Frame):
    """Tek bir müşterinin hesabı: özet kutuları, işlem düğmeleri ve işlem listesi.

    yil_getir: gösterilecek yıl (None = tüm yıllar)
    yil_ayarla: kaydedilen fiş başka bir yıldaysa o yılı açmak için çağrılır
    islem_tablosu: False ise sadece özet ve düğmeler gösterilir (fiş ekranı kendi tablosunu kullanır)
    """

    def __init__(self, ana, uyg, yil_getir, yil_ayarla, bos_metin, islem_tablosu=True):
        super().__init__(ana)
        self.uyg, self.db = uyg, uyg.db
        self.yil_getir, self.yil_ayarla, self.bos_metin = yil_getir, yil_ayarla, bos_metin
        self.mid = None

        baslik_satiri = ttk.Frame(self)
        baslik_satiri.pack(fill="x")
        self.baslik = ttk.Label(baslik_satiri, text=bos_metin, style="Baslik.TLabel")
        self.baslik.pack(side="left")
        musteri_dugmeleri = [
            ttk.Button(baslik_satiri, text="Müşteriyi Sil", command=self.musteri_sil),
            ttk.Button(baslik_satiri, text="Müşteriyi Düzenle", command=self.musteri_duzenle),
        ]
        for b in musteri_dugmeleri:
            b.pack(side="right", padx=(6, 0))
        self.bilgi = ttk.Label(self, text="")
        self.bilgi.pack(anchor="w")

        ozet = ttk.Frame(self)
        ozet.pack(fill="x", pady=8)
        self.ozet_kutu, self.ozet_lbl = {}, {}
        for k, baslik in (("devir", "Önceki Yıldan Devir"), ("satis", "Toplam Satış"),
                          ("tahsilat", "Toplam Tahsilat"), ("kalan", "Kalan Borç")):
            self.ozet_kutu[k] = ttk.LabelFrame(ozet, text=baslik, padding=(10, 4))
            self.ozet_kutu[k].pack(side="left", padx=(0, 8))
            self.ozet_lbl[k] = ttk.Label(self.ozet_kutu[k], text="-", style="Bakiye.TLabel", width=15, anchor="e")
            self.ozet_lbl[k].pack()

        butonlar = ttk.Frame(self)
        butonlar.pack(fill="x")
        self.dugmeler = [
            ttk.Button(butonlar, text="WhatsApp / Ekstre Gönder", style="Vurgu.TButton",
                       command=self.ekstre_gonder),
            ttk.Button(butonlar, text="+ Satış Yap", command=self.yeni_satis),
            ttk.Button(butonlar, text="+ Tahsilat (Ödeme Al)", command=self.yeni_tahsilat),
        ]
        if islem_tablosu:
            self.dugmeler += [
                ttk.Button(butonlar, text="Fişi / İşlemi Düzenle", command=self.islem_duzenle),
                ttk.Button(butonlar, text="İşlemi Sil", command=self.islem_sil),
            ]
        for b in self.dugmeler:
            b.pack(side="left", padx=(0, 6))
        self.dugmeler += musteri_dugmeleri

        self.itv = None
        if islem_tablosu:
            self._islem_tablosu_kur()
        self.temizle()

    def _islem_tablosu_kur(self):
        ttk.Label(self, text="İşlemler  —  ▸ ile fişteki ürünleri görün, düzeltmek için fişe çift tıklayın:").pack(
            anchor="w", pady=(10, 2))
        kap, self.itv = tablo(self, [("tarih", "Tarih", 80, "w"), ("tur", "Tür", 62, "w"),
                                     ("adet", "Adet", 45, "e"), ("fiyat", "Birim Fiyat", 88, "e"),
                                     ("borc", "Borç", 92, "e"), ("alacak", "Ödeme", 92, "e"),
                                     ("bakiye", "Bakiye", 98, "e")], agac=True)
        kap.pack(fill="both", expand=True)
        self.itv.heading("#0", text="Fiş / Ürün")
        self.itv.column("#0", width=170)
        self.itv.bind("<Double-1>", self.islem_cift_tik)
        self.itv.tag_configure("satis", foreground=KIRMIZI)
        self.itv.tag_configure("tahsilat", foreground=YESIL)
        self.itv.tag_configure("kalem", foreground="#555555")
        self.itv.tag_configure("devir", background=ACIK_TURUNCU, foreground="#5A3A12")

    def goster(self, mid):
        self.mid = mid
        for b in self.dugmeler:
            b.state(["!disabled"])
        self.yenile()

    def temizle(self):
        self.mid = None
        if self.itv:
            self.itv.delete(*self.itv.get_children())
        self.baslik.config(text=self.bos_metin)
        self.bilgi.config(text="")
        for l in self.ozet_lbl.values():
            l.config(text="-", foreground="")
        for b in self.dugmeler:
            b.state(["disabled"])

    def yenile(self):
        if self.mid is None or self.db.musteri(self.mid) is None:
            self.temizle()
            return
        if self.itv:
            self.itv.delete(*self.itv.get_children())
        ekle = self.itv.insert if self.itv else (lambda *a, **k: None)   # tablosuz panelde sadece özet
        _, ad, tel, notlar = self.db.musteri(self.mid)
        self.baslik.config(text=ad)
        self.bilgi.config(text="   ".join(x for x in (f"Tel: {tel}" if tel else "", notlar) if x))

        yil = self.yil_getir()
        if yil:
            self.ozet_kutu["devir"].config(text="Önceki Yıldan Devir")
            self.ozet_kutu["devir"].pack(side="left", padx=(0, 8), before=self.ozet_kutu["satis"])
            self.ozet_kutu["satis"].config(text=f"{yil} Satış")
            self.ozet_kutu["tahsilat"].config(text=f"{yil} Tahsilat")
        else:                                 # tüm yıllar: devir yok
            self.ozet_kutu["devir"].pack_forget()
            self.ozet_kutu["satis"].config(text="Toplam Satış")
            self.ozet_kutu["tahsilat"].config(text="Toplam Tahsilat")

        devir = bakiye = self.db.devir(self.mid, yil) if yil else 0
        top_satis = top_tahsilat = 0
        if abs(devir) > 0.005:
            ekle("", "end", iid="devir", text=f"{yil - 1} yılından devir", tags=("devir",),
                 values=(f"01.01.{yil}", "Devir", "", "",
                         para(devir) if devir > 0 else "", para(-devir) if devir < 0 else "",
                         para(devir)))
        for iid, tur, tarih, tutar, aciklama, fis_no in self.db.islemler(self.mid, yil):
            if tur == "SATIŞ":
                bakiye += tutar
                top_satis += tutar
                if not self.itv:
                    continue
                kalemler = self.db.kalemler(iid)
                ozet = f"Fiş {fis_no}" + (f"  –  {aciklama}" if aciklama else "")
                ust = ekle("", "end", iid=str(iid), text=ozet, tags=("satis",),
                           values=(tarih_goster(tarih), "Satış", "", "",
                                   para(tutar), "", para(bakiye)))
                for urun, adet, fiyat in kalemler:
                    ekle(ust, "end", text="   " + urun, tags=("kalem",),
                         values=("", "", f"{adet:g}", para(fiyat), para(adet * fiyat), "", ""))
            else:
                bakiye -= tutar
                top_tahsilat += tutar
                ekle("", "end", iid=str(iid), text=aciklama or "Ödeme", tags=("tahsilat",),
                     values=(tarih_goster(tarih), "Tahsilat", "", "", "", para(tutar), para(bakiye)))
        self.ozet_lbl["devir"].config(text=para(devir))
        self.ozet_lbl["satis"].config(text=para(top_satis))
        self.ozet_lbl["tahsilat"].config(text=para(top_tahsilat))
        self.ozet_lbl["kalan"].config(text=para(bakiye), foreground=KIRMIZI if bakiye > 0.005 else YESIL)
        if self.itv and self.itv.get_children():
            self.itv.see(self.itv.get_children()[-1])

    # --- işlemler
    def yeni_satis(self):
        SatisPenceresi(self.uyg, self.db, self.mid, self.satis_kaydedildi)

    def satis_kaydedildi(self, mid, tarih):
        """Fiş görüntülenen yıldan başka bir yıla kaydedildiyse o yılı açar ki fiş görünsün."""
        yil = int(tarih[:4])
        if self.yil_getir() not in (None, yil):
            self.yil_ayarla(yil)
        self.goster(mid)
        self.uyg.degisti()

    def yeni_tahsilat(self):
        TahsilatPenceresi(self.uyg, self.db, self.mid, self.uyg.degisti)

    def ekstre_gonder(self):
        try:
            import ekstre
        except ImportError:
            messagebox.showerror("Ekstre", "Görsel/PDF için şu komutu çalıştırın:\n\npip install pillow")
            return
        ekstre.EkstrePenceresi(self.uyg, self.db, self.mid, self.yil_getir() or date.today().year,
                               self.uyg.degisti)

    def musteri_duzenle(self):
        MusteriPenceresi(self.uyg, self.db, self.mid, kaydedildi=lambda mid: self.uyg.degisti())

    def musteri_sil(self):
        ad = self.db.musteri(self.mid)[1]
        if not messagebox.askyesno("Müşteriyi Sil", f"'{ad}' ve TÜM işlemleri silinecek. Emin misiniz?"):
            return
        self.db.musteri_sil(self.mid)
        self.temizle()
        self.uyg.degisti()

    def islem_cift_tik(self, e):
        if self.itv.identify_row(e.y):
            self.islem_duzenle()
            return "break"                    # çift tık fişi açıp kapatmasın

    def secili_islem(self, baslik):
        s = self.itv.selection()
        if not s:
            messagebox.showinfo(baslik, "Listeden bir fiş veya tahsilat seçin.")
            return None
        iid = self.itv.parent(s[0]) or s[0]   # ürün satırı seçildiyse ait olduğu fiş
        if iid == "devir":
            messagebox.showinfo("Devir", "Devir tutarı önceki yılların işlemlerinden otomatik hesaplanır.\n"
                                         "Değiştirmek için ilgili yılı seçip o yılın fişlerini düzenleyin.")
            return None
        return iid

    def islem_duzenle(self):
        iid = self.secili_islem("Düzenle")
        if iid is None:
            return
        if "satis" in self.itv.item(iid, "tags"):
            SatisPenceresi(self.uyg, self.db, self.mid, self.satis_kaydedildi, iid=int(iid))
        else:
            TahsilatPenceresi(self.uyg, self.db, self.mid, self.uyg.degisti, iid=int(iid))

    def islem_sil(self):
        iid = self.secili_islem("İşlem Sil")
        if iid is None or not messagebox.askyesno("İşlem Sil", "Seçili işlem silinsin mi?"):
            return
        self.db.islem_sil(int(iid))
        self.uyg.degisti()


# ---------------------------------------------------------------- ekranlar
class AnaEkran(tk.Frame):
    """Açılış ekranı: logo ve FİŞ / CARİ düğmeleri."""

    def __init__(self, ana, uyg):
        super().__init__(ana, bg="white")
        orta = tk.Frame(self, bg="white")
        orta.place(relx=0.5, rely=0.46, anchor="center")
        self.logo = logo_yukle(uyg, 230)
        if self.logo:
            tk.Label(orta, image=self.logo, bg="white").pack()
        tk.Label(orta, text=FIRMA, font=("Segoe UI", 34, "bold"), fg=TURUNCU, bg="white").pack(pady=(10, 0))
        tk.Label(orta, text="Cari Hesap Takip", font=("Segoe UI", 13), fg="#8a7a6a", bg="white").pack()
        dugmeler = tk.Frame(orta, bg="white")
        dugmeler.pack(pady=(36, 0))
        for metin, aciklama, sayfa in [("FİŞ", "Satış fişi kes, tahsilat al", "fis"),
                                       ("CARİ", "Müşteri hesapları, ekstre, WhatsApp", "cari")]:
            kutu = tk.Frame(dugmeler, bg="white")
            kutu.pack(side="left", padx=24)
            ttk.Button(kutu, text=metin, style="Buyuk.TButton", width=9,
                       command=lambda s=sayfa: uyg.sayfa_goster(s)).pack()
            tk.Label(kutu, text=aciklama, font=("Segoe UI", 10), fg="#8a7a6a", bg="white").pack(pady=(8, 0))
        ttk.Button(orta, text="Sunucu Ayarları", command=uyg.sunucu_ayarlari).pack(pady=(26, 0), ipadx=20, ipady=4)


class SonIslemler(ttk.Frame):
    """Tüm müşterilerin son girilen fiş ve tahsilatları, en son girilen en üstte.

    Girilme sırasına göredir (fiş tarihine göre değil): defterden geçirirken nerede kalındığı görünür.
    """
    ADET = 300

    def __init__(self, ana, uyg, mid_getir):
        super().__init__(ana)
        self.uyg, self.db, self.mid_getir = uyg, uyg.db, mid_getir
        self.satir = {}                       # tablo satırı -> (islem_id, tür, musteri_id, fiş no, müşteri)

        ust = ttk.Frame(self)
        ust.pack(fill="x", pady=(0, 4))
        ttk.Label(ust, text="Son Girilen İşlemler", font=("Segoe UI", 12, "bold"),
                  foreground="#3A2A1A").pack(side="left")
        self.son_lbl = ttk.Label(ust, text="", font=("Segoe UI", 10, "bold"), foreground=KOYU_TURUNCU)
        self.son_lbl.pack(side="left", padx=14)
        ttk.Button(ust, text="Seçili İşlemi Sil", command=self.sil).pack(side="right")
        ttk.Button(ust, text="Seçili Fişi Düzenle", command=self.duzenle).pack(side="right", padx=6)
        self.sadece = tk.BooleanVar(uyg, value=False)
        ttk.Checkbutton(ust, text="Sadece seçili müşteri", variable=self.sadece,
                        command=self.yenile).pack(side="right", padx=10)

        kap, self.tv = tablo(self, [("fis", "Fiş No", 70, "center"), ("tarih", "Tarih", 95, "w"),
                                    ("musteri", "Müşteri", 190, "w"), ("tur", "Tür", 75, "w"),
                                    ("urun", "Ürün / Açıklama", 210, "w"), ("adet", "Adet", 60, "e"),
                                    ("fiyat", "Birim Fiyat", 100, "e"), ("tutar", "Tutar", 115, "e")],
                             agac=True)
        kap.pack(fill="both", expand=True)
        self.tv.column("#0", width=28, minwidth=28, stretch=False)
        self.tv.heading("urun", text="Ürünler (görmek için fişe tıklayın)")
        self.tv.tag_configure("a", background="white")
        self.tv.tag_configure("b", background="#FBF5EF")
        self.tv.tag_configure("son", background=ACIK_TURUNCU, font=("Segoe UI", 10, "bold"))
        self.tv.tag_configure("tahsilat", foreground=YESIL)
        self.tv.tag_configure("kalem", foreground="#555555", background="#FFFDFB")
        self.tv.bind("<ButtonRelease-1>", self.tikla)
        self.tv.bind("<Double-1>", self.cift_tikla)
        self.tv.bind("<Delete>", lambda e: self.sil())

    def tikla(self, e):
        """Fiş satırına tıklayınca ürünleri aç/kapat (oktaki tıklamayı Tk kendisi yapar)."""
        satir = self.tv.identify_row(e.y)
        if satir and self.tv.identify_region(e.x, e.y) != "tree" and self.tv.get_children(satir):
            self.tv.item(satir, open=not self.tv.item(satir, "open"))

    def cift_tikla(self, e):
        satir = self.tv.identify_row(e.y)
        if satir:
            ust = self.tv.parent(satir) or satir
            self.tv.item(ust, open=True)
            self.duzenle()
            return "break"

    def yenile(self):
        mid = self.mid_getir() if self.sadece.get() else None
        self.tv.delete(*self.tv.get_children())
        self.satir = {}
        satirlar = self.db.son_islemler(self.ADET, mid)
        # her işlem tek satır (fiş no, tarih, müşteri, toplam); ürünler tıklayınca açılan alt satırlar
        fisler = {}
        for iid, fis_no, tarih, ad, tur, urun, adet, fiyat, tutar, aciklama, musteri_id in satirlar:
            f = fisler.setdefault(iid, {"bilgi": (fis_no, tarih, ad, tur, tutar, aciklama, musteri_id),
                                        "kalemler": []})
            if urun is not None:
                f["kalemler"].append((urun, adet, fiyat))
        for sira, (iid, f) in enumerate(fisler.items(), 1):
            fis_no, tarih, ad, tur, tutar, aciklama, musteri_id = f["bilgi"]
            bant = "son" if sira == 1 else ("a" if sira % 2 else "b")
            if tur == "SATIŞ":
                n = len(f["kalemler"])
                ozet = f["kalemler"][0][0] if n == 1 else f"{n} ürün"
                if aciklama:
                    ozet += f"  ({aciklama})"
                ust = self.tv.insert("", "end", tags=(bant,),
                                     values=(fis_no, tarih_goster(tarih), ad, "Satış", ozet, "", "", para(tutar)))
                for urun, adet, fiyat in f["kalemler"]:
                    self.tv.insert(ust, "end", tags=("kalem",),
                                   values=("", "", "", "", "• " + urun, f"{adet:g}".replace(".", ","),
                                           para(fiyat), para(adet * fiyat)))
            else:
                ust = self.tv.insert("", "end", tags=(bant, "tahsilat"),
                                     values=("", tarih_goster(tarih), ad, "Tahsilat", aciklama or "Ödeme",
                                             "", "", para(tutar)))
            self.satir[ust] = (iid, tur, musteri_id, fis_no, ad)

        if satirlar:
            iid, fis_no, tarih, ad, tur, *_, tutar, _, _ = satirlar[0]
            ne = f"Fiş {fis_no}" if tur == "SATIŞ" else "Tahsilat"
            self.son_lbl.config(text=f"En son girilen:  {ne}  ·  {ad}  ·  {tarih_goster(tarih)}  ·  {para(tutar)}")
        else:
            self.son_lbl.config(text="Henüz işlem girilmedi")

    def secili(self, baslik):
        s = self.tv.selection()
        if not s:
            messagebox.showinfo(baslik, "Listeden bir satır seçin.")
            return None
        return self.satir[self.tv.parent(s[0]) or s[0]]   # ürün satırı seçildiyse ait olduğu fiş

    def duzenle(self):
        secim = self.secili("Düzenle")
        if not secim:
            return
        iid, tur, mid, _, _ = secim
        if tur == "SATIŞ":
            SatisPenceresi(self.uyg, self.db, mid, lambda m, t: self.uyg.degisti(), iid=iid)
        else:
            TahsilatPenceresi(self.uyg, self.db, mid, self.uyg.degisti, iid=iid)

    def sil(self):
        secim = self.secili("İşlem Sil")
        if not secim:
            return
        iid, tur, _, fis_no, ad = secim
        ne = f"Fiş {fis_no}" if tur == "SATIŞ" else "Tahsilat"
        if messagebox.askyesno("İşlem Sil", f"{ne} ({ad}) silinsin mi?"):
            self.db.islem_sil(iid)
            self.uyg.degisti()


class FisEkrani(ttk.Frame):
    """Satış ekranı: sadece adı yazılıp seçilen müşterinin hesabı görünür."""

    def __init__(self, ana, uyg):
        super().__init__(ana)
        self.uyg, self.db = uyg, uyg.db

        arac = ttk.Frame(self, padding=(8, 8, 8, 0))
        arac.pack(fill="x")
        ttk.Button(arac, text="+ Yeni Satış", style="Vurgu.TButton",
                   command=lambda: self.detay.yeni_satis()).pack(side="left", padx=(0, 6))
        ttk.Button(arac, text="+ Yeni Müşteri", command=self.yeni_musteri).pack(side="left", padx=(0, 6))
        ttk.Button(arac, text="Bilanço / Raporlar", command=uyg.bilanco_ac).pack(side="left")
        ttk.Button(arac, text="Boş Excel Şablonu", command=uyg.excel_sablon).pack(side="right")
        ttk.Button(arac, text="Excel'den Satış Al", command=uyg.excel_ice_aktar).pack(side="right", padx=6)
        ttk.Button(arac, text="Excel'e Aktar", command=uyg.excel_disa_aktar).pack(side="right")

        ara = ttk.Frame(self, padding=(8, 12, 8, 0))
        ara.pack(fill="x")
        ttk.Label(ara, text="Müşteri:", font=("Segoe UI", 12, "bold")).pack(side="left")
        self.ara = tk.StringVar(uyg)
        self.giris = OneriGiris(ara, self.db.musteri_adlari, self.secildi, textvariable=self.ara,
                                width=36, font=("Segoe UI", 12))
        self.giris.pack(side="left", padx=8, ipady=2)
        self.giris.bind("<Return>", self.enter, add="+")
        ttk.Button(ara, text="Temizle", command=self.temizle).pack(side="left")
        self.yil_var = tk.StringVar(uyg, value=str(uyg.yil))
        self.yil_cb = ttk.Combobox(ara, textvariable=self.yil_var, state="readonly", width=6,
                                   font=("Segoe UI", 12, "bold"), values=self.db.yillar())
        self.yil_cb.pack(side="right")
        self.yil_cb.bind("<<ComboboxSelected>>", self.yil_degisti)
        ttk.Label(ara, text="Çalışma Yılı:", font=("Segoe UI", 11)).pack(side="right", padx=4)

        self.detay = MusteriDetay(self, uyg, lambda: uyg.yil, self.yil_ayarla,
                                  "Müşteri adını yazıp listeden seçin", islem_tablosu=False)
        self.detay.pack(fill="x", padx=8, pady=(8, 4))
        self.son = SonIslemler(self, uyg, lambda: self.detay.mid)
        self.son.pack(fill="both", expand=True, padx=8, pady=(6, 8))
        self.son.yenile()

    def musteri_goster(self, mid):
        self.detay.goster(mid)
        if self.son.sadece.get():
            self.son.yenile()

    def secildi(self, ad):
        mid = self.db.musteri_bul(ad)
        if mid is not None:
            self.musteri_goster(mid)

    def enter(self, _):
        ad = self.ara.get().strip()
        if not ad or self.giris.acik():
            return
        mid = self.db.musteri_bul(ad)
        if mid is None:
            messagebox.showinfo("Müşteri", f"'{ad}' adlı müşteri kayıtlı değil.\n"
                                           "'+ Yeni Satış' ile bu adı yazarsanız otomatik eklenir.")
        else:
            self.musteri_goster(mid)

    def temizle(self):
        self.ara.set("")
        self.giris.gizle()
        self.detay.temizle()
        if self.son.sadece.get():
            self.son.yenile()
        self.giris.focus_set()

    def yil_ayarla(self, yil):
        self.uyg.yil = yil
        self.yil_var.set(str(yil))

    def yil_degisti(self, _=None):
        self.uyg.yil = int(self.yil_var.get())
        self.detay.yenile()

    def yeni_musteri(self):
        def kaydedildi(mid):
            self.ara.set(self.db.musteri(mid)[1])
            self.musteri_goster(mid)
            self.uyg.degisti()
        MusteriPenceresi(self.uyg, self.db, kaydedildi=kaydedildi)

    def yenile(self):
        self.yil_cb["values"] = self.db.yillar()
        self.detay.yenile()
        self.son.yenile()
        # satış kaydından sonra başka müşteri gösterildiyse arama kutusu da onun adını alsın
        if self.detay.mid is not None and self.detay.mid != getattr(self, "_gosterilen", None):
            self._gosterilen = self.detay.mid
            self.ara.set(self.db.musteri(self.detay.mid)[1])
            self.giris.gizle()


class CariEkrani(ttk.Frame):
    """Tüm müşteriler ve bakiyeleri; seçilen müşterinin bütün işlemleri."""
    TUMU = "Tüm Yıllar"

    def __init__(self, ana, uyg):
        super().__init__(ana)
        self.uyg, self.db = uyg, uyg.db
        # sol liste sabit genişlikte: sürüklenebilir bölme açılışta sıfıra inip listeyi gizleyebiliyordu
        sol = ttk.Frame(self, width=370)
        sol.pack(side="left", fill="y", padx=(8, 0), pady=8)
        sol.pack_propagate(False)
        ust = ttk.Frame(sol)
        ust.pack(fill="x")
        ttk.Label(ust, text="Ara:").pack(side="left")
        self.ara = tk.StringVar(uyg)
        self.ara.trace_add("write", lambda *a: self.liste_yenile())
        ttk.Entry(ust, textvariable=self.ara).pack(side="left", fill="x", expand=True, padx=4)
        self.yil_var = tk.StringVar(uyg, value=self.TUMU)
        self.yil_cb = ttk.Combobox(ust, textvariable=self.yil_var, state="readonly", width=10)
        self.yil_cb.pack(side="left")
        self.yil_cb.bind("<<ComboboxSelected>>", self.yil_degisti)

        kap, self.mtv = tablo(sol, [("ad", "Müşteri", 140, "w"), ("tel", "Telefon", 95, "w"),
                                    ("bakiye", "Borç", 100, "e")])
        kap.pack(fill="both", expand=True, pady=(6, 0))
        self.mtv.configure(selectmode="browse")
        self.mtv.tag_configure("borclu", foreground=KIRMIZI)
        self.mtv.tag_configure("alacakli", foreground=YESIL)
        self.mtv.bind("<<TreeviewSelect>>", self.musteri_secildi)
        self.genel_lbl = ttk.Label(sol, text="")
        self.genel_lbl.pack(anchor="e", pady=(4, 0))
        alt = ttk.Frame(sol)
        alt.pack(fill="x", pady=(4, 0))
        ttk.Button(alt, text="+ Yeni Müşteri", command=self.yeni_musteri).pack(side="left")
        ttk.Button(alt, text="Excel'e Aktar", command=uyg.excel_disa_aktar).pack(side="right")

        self.detay = MusteriDetay(self, uyg, self.yil, self.yil_ayarla, "Soldan bir müşteri seçin")
        self.detay.pack(side="left", fill="both", expand=True, padx=(14, 8), pady=8)
        self.yenile()

    def yil(self):
        v = self.yil_var.get()
        return None if v == self.TUMU else int(v)

    def yil_ayarla(self, yil):
        self.yil_var.set(str(yil))
        self.liste_yenile()

    def yil_degisti(self, _=None):
        self.liste_yenile()
        self.detay.yenile()

    def liste_yenile(self):
        sec = self.detay.mid
        yil = self.yil()
        self.mtv.delete(*self.mtv.get_children())
        toplam = 0
        for mid, ad, tel, devir, satis, tahsilat in self.db.musteriler(self.ara.get().strip(), yil):
            bakiye = devir + satis - tahsilat
            toplam += bakiye
            etiket = "borclu" if bakiye > 0.005 else ("alacakli" if bakiye < -0.005 else "")
            self.mtv.insert("", "end", iid=str(mid), values=(ad, tel, para(bakiye)), tags=(etiket,))
        gecmis = yil is not None and yil < date.today().year
        self.mtv.heading("bakiye", text=f"{yil} Sonu Borç" if gecmis else "Borç")
        self.genel_lbl.config(text=(f"{yil} sonu toplam alacak: " if gecmis else "Toplam alacak: ") + para(toplam))
        if sec is not None and self.mtv.exists(str(sec)):
            self.mtv.selection_set(str(sec))
            self.mtv.see(str(sec))

    def musteri_secildi(self, _=None):
        s = self.mtv.selection()
        if s and int(s[0]) != self.detay.mid:
            self.detay.goster(int(s[0]))

    def musteri_ac(self, mid):
        self.ara.set("")
        self.detay.goster(mid)
        self.liste_yenile()

    def yeni_musteri(self):
        MusteriPenceresi(self.uyg, self.db, kaydedildi=lambda mid: (self.musteri_ac(mid), self.uyg.degisti()))

    def yenile(self):
        self.yil_cb["values"] = [self.TUMU] + self.db.yillar()
        self.liste_yenile()
        self.detay.yenile()


# ---------------------------------------------------------------- ana pencere
class Uygulama(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = DB(DB_PATH)
        self.bilanco = None
        self.yil = date.today().year         # fiş ekranındaki çalışma yılı
        self.bugun_yil = self.yil
        self.title(f"{FIRMA} - Cari Hesap Takip")
        self.geometry("1200x740")
        self.minsize(980, 600)
        tema_uygula(self)
        simge = logo_yukle(self, 64)
        if simge:
            self.iconphoto(True, simge)
            self._simge = simge

        # --- logolu başlık (ana ekranda gizli)
        self.ust = tk.Frame(self, bg="white")
        bas = tk.Frame(self.ust, bg="white")
        bas.pack(fill="x")
        self.logo = logo_yukle(self, 54)
        if self.logo:
            tk.Label(bas, image=self.logo, bg="white").pack(side="left", padx=(12, 8), pady=6)
        tk.Label(bas, text=FIRMA, font=("Segoe UI", 20, "bold"), fg=TURUNCU, bg="white").pack(side="left")
        self.sayfa_lbl = tk.Label(bas, text="", font=("Segoe UI", 16, "bold"), fg="#5A3A12", bg="white")
        self.sayfa_lbl.pack(side="left", padx=(18, 0))
        ttk.Button(bas, text="◀  Ana Ekran", command=lambda: self.sayfa_goster("ana")).pack(
            side="right", padx=12)
        ttk.Button(bas, text="Sunucu", command=self.sunucu_ayarlari).pack(side="right")
        tk.Frame(self.ust, bg=TURUNCU, height=4).pack(fill="x")
        import bulut
        self.bulut = bulut.BulutEsitleyici(self)
        self.bulut.durum_lbl = tk.Label(bas, text="", font=("Segoe UI", 10, "bold"), bg="white", cursor="hand2")
        self.bulut.durum_lbl.pack(side="right", padx=12)
        self.bulut.durum_lbl.bind("<Button-1>", lambda e: self.sunucu_ayarlari())

        self.govde = ttk.Frame(self)
        self.govde.pack(fill="both", expand=True)
        self.govde.rowconfigure(0, weight=1)
        self.govde.columnconfigure(0, weight=1)
        self.fis = FisEkrani(self.govde, self)
        self.cari = CariEkrani(self.govde, self)
        self.sayfalar = {"ana": AnaEkran(self.govde, self), "fis": self.fis, "cari": self.cari}
        for s in self.sayfalar.values():
            s.grid(row=0, column=0, sticky="nsew")
        self.sayfa_goster("ana")
        self.after(60_000, self.yil_kontrol)
        self.after(2500, lambda: __import__("db_tarama").tara_ve_sor(self))   # masaüstündeki eski veritabanları

    def yil_kontrol(self):
        """Program açıkken yeni yıla girilirse (31 Aralık → 1 Ocak) çalışma yılını kendiliğinden ilerletir."""
        yeni = date.today().year
        if yeni != self.bugun_yil:
            eski, self.bugun_yil = self.bugun_yil, yeni
            if self.yil == eski:              # kullanıcı geçmiş bir yıla bakıyorsa dokunma
                self.fis.yil_ayarla(yeni)
            self.degisti()
        self.after(60_000, self.yil_kontrol)

    def sayfa_goster(self, ad):
        if ad == "ana":
            self.ust.pack_forget()
            self.fis.temizle()                # ana ekrana dönünce son bakılan müşteri ekranda kalmasın
        else:
            self.ust.pack(fill="x", before=self.govde)
            self.sayfa_lbl.config(text={"fis": "FİŞ", "cari": "CARİ HESAPLAR"}[ad])
        self.sayfalar[ad].tkraise()
        if ad == "fis":
            self.fis.giris.focus_set()
        elif ad == "cari":
            self.cari.yenile()

    def cari_ac(self, mid):
        """Bilanço ekranından çift tıklanan müşteriyi Cari ekranında açar."""
        self.sayfa_goster("cari")
        self.cari.musteri_ac(mid)
        self.lift()

    def yenile_ekranlar(self):
        self.fis.yenile()
        self.cari.yenile()
        if self.bilanco and self.bilanco.winfo_exists():
            self.bilanco.yenile()

    def degisti(self):
        """Kullanıcı bir şey değiştirdi: ekranları yenile, birkaç saniye sonra sunucuya gönder."""
        self.yenile_ekranlar()
        self.bulut.tetikle(3000)

    def sunucu_ayarlari(self):
        import bulut
        bulut.SunucuAyarPenceresi(self)

    def bilanco_ac(self):
        if self.bilanco and self.bilanco.winfo_exists():
            self.bilanco.yenile()
            self.bilanco.lift()
            self.bilanco.focus_force()
        else:
            self.bilanco = BilancoPenceresi(self, self.db, self.cari_ac)

    # --- excel
    def excel_modulu(self):
        try:
            import excel_aktar
            return excel_aktar
        except ImportError:
            messagebox.showerror("Excel", "Excel desteği için şu komutu çalıştırın:\n\npip install openpyxl")
            return None

    def excel_kaydet(self, islem, varsayilan_ad):
        ex = self.excel_modulu()
        if not ex:
            return
        yol = filedialog.asksaveasfilename(parent=self, defaultextension=".xlsx",
                                           initialfile=varsayilan_ad,
                                           filetypes=[("Excel dosyası", "*.xlsx")])
        if not yol:
            return
        try:
            islem(ex, yol)
        except PermissionError:
            messagebox.showerror("Excel", "Dosya yazılamadı. Excel'de açıksa kapatıp tekrar deneyin.")
            return
        if messagebox.askyesno("Excel", f"Dosya kaydedildi:\n{yol}\n\nŞimdi açılsın mı?"):
            os.startfile(yol)

    def excel_disa_aktar(self):
        self.excel_kaydet(lambda ex, yol: ex.disa_aktar(self.db, yol),
                          f"muhasebe_{date.today().isoformat()}.xlsx")

    def excel_sablon(self):
        self.excel_kaydet(lambda ex, yol: ex.sablon_olustur(yol), "satis_sablonu.xlsx")

    def excel_ice_aktar(self):
        ex = self.excel_modulu()
        if not ex:
            return
        yol = filedialog.askopenfilename(parent=self, filetypes=[("Excel dosyası", "*.xlsx *.xlsm")])
        if not yol:
            return
        try:
            satislar, tahsilatlar, uyarilar = ex.oku(yol)
        except Exception as e:
            messagebox.showerror("Excel", f"Dosya okunamadı:\n{e}")
            return
        uyari_metni = ""
        if uyarilar:
            uyari_metni = f"\n\nAtlanan {len(uyarilar)} satır:\n" + "\n".join(uyarilar[:8]) + (
                "\n..." if len(uyarilar) > 8 else "")
        if not satislar and not tahsilatlar:
            messagebox.showwarning(
                "Excel", "Dosyada okunacak satış bulunamadı.\n\nBaşlık satırında en az şu sütunlar olmalı: "
                         "Tarih, Müşteri, Ürün, Adet, Birim Fiyat.\n"
                         "'Boş Excel Şablonu' düğmesiyle örnek dosya oluşturabilirsiniz." + uyari_metni)
            return

        adlar = {kucuk(k["musteri"].strip()) for k in satislar + tahsilatlar}
        yeni = sum(1 for a in adlar if self.db.musteri_bul(a) is None)
        kalem = sum(len(s["kalemler"]) for s in satislar)
        tekrar_s = [s for s in satislar if ex.zaten_var(self.db, s, True)]
        tekrar_t = [t for t in tahsilatlar if ex.zaten_var(self.db, t, False)]
        mesaj = (f"{len(satislar)} satış ({kalem} ürün satırı) ve {len(tahsilatlar)} tahsilat bulundu.\n"
                 f"{yeni} yeni müşteri otomatik oluşturulacak." + uyari_metni)
        if tekrar_s or tekrar_t:
            cevap = messagebox.askyesnocancel(
                "Excel'den Al", mesaj + f"\n\nDİKKAT: {len(tekrar_s)} satış ve {len(tekrar_t)} tahsilat "
                                        "programda zaten var gibi görünüyor (aynı müşteri, tarih, tutar).\n\n"
                                        "Evet: Bunları atla, sadece yenileri ekle\n"
                                        "Hayır: Hepsini ekle\nİptal: Hiçbir şey ekleme")
            if cevap is None:
                return
            if cevap:
                satislar = [s for s in satislar if s not in tekrar_s]
                tahsilatlar = [t for t in tahsilatlar if t not in tekrar_t]
        elif not messagebox.askyesno("Excel'den Al", mesaj + "\n\nKayıtlar eklensin mi?"):
            return
        yeni = ex.kaydet(self.db, satislar, tahsilatlar)
        self.degisti()
        messagebox.showinfo("Excel'den Al", f"{len(satislar)} satış ve {len(tahsilatlar)} tahsilat eklendi.\n"
                                            f"{yeni} yeni müşteri oluşturuldu.")


if __name__ == "__main__":
    Uygulama().mainloop()
