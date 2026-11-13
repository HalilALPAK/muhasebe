"""Müşteri hesap ekstresi: logolu görsel (PNG) + PDF oluşturma ve WhatsApp ile gönderme."""
import os
import re
import subprocess
import tkinter as tk
import urllib.parse
from datetime import datetime
from functools import lru_cache
from tkinter import ttk, messagebox

from PIL import Image, ImageDraw, ImageFont, ImageTk

from muhasebe import (FIRMA, KLASOR, LOGO_PATH, TURUNCU, KOYU_TURUNCU, ACIK_TURUNCU, YESIL,
                      para, tarih_goster)

EKSTRE_KLASORU = os.path.join(KLASOR, "Ekstreler")
W, H, M = 1240, 1754, 70                     # A4, 150 dpi
KOYU, GRI = "#2A1A0A", "#666666"
KOLONLAR = [("Tarih", 120, "l"), ("İşlem / Ürün", 270, "l"), ("Adet", 65, "r"),
            ("Birim Fiyat", 125, "r"), ("Tutar", 130, "r"), ("Borç", 130, "r"),
            ("Ödeme", 125, "r"), ("Bakiye", 135, "r")]
FONT_KLASORU = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


# ---------------------------------------------------------------- veri
def veri(db, mid, yil=None):
    """Ekstre içeriği. yil verilirse önceki yıllar devir olarak tek satıra iner."""
    _, ad, tel, _ = db.musteri(mid)
    devir = db.devir(mid, yil) if yil else 0
    bakiye, satis, tahsilat, islemler = devir, 0, 0, []
    for iid, tur, tarih, tutar, aciklama, fis_no in db.islemler(mid, yil):
        if tur == "SATIŞ":
            bakiye += tutar
            satis += tutar
        else:
            bakiye -= tutar
            tahsilat += tutar
        islemler.append((tur, tarih, tutar, aciklama, fis_no,
                         db.kalemler(iid) if tur == "SATIŞ" else [], bakiye))
    return {"ad": ad, "tel": tel, "yil": yil, "devir": devir, "satis": satis,
            "tahsilat": tahsilat, "bakiye": bakiye, "islemler": islemler}


# ---------------------------------------------------------------- çizim
@lru_cache(maxsize=None)
def font(boyut, kalin=False):
    for ad in (("segoeuib.ttf", "arialbd.ttf") if kalin else ("segoeui.ttf", "arial.ttf")):
        try:
            return ImageFont.truetype(os.path.join(FONT_KLASORU, ad), boyut)
        except OSError:
            pass
    return ImageFont.load_default(boyut)


def yaz(d, x, y, metin, boyut, kalin=False, renk=KOYU, hiza="l", genislik=None):
    """y dikey ortadır. Sığmayan metin küçültülür, yine sığmazsa kısaltılır."""
    f = font(boyut, kalin)
    if genislik:
        while d.textlength(metin, font=f) > genislik and boyut > 13:
            boyut -= 1
            f = font(boyut, kalin)
        while d.textlength(metin, font=f) > genislik and len(metin) > 1:
            metin = metin[:-2] + "…"
    w = d.textlength(metin, font=f)
    x = x - w if hiza == "r" else (x - w / 2 if hiza == "c" else x)
    d.text((x, y), metin, font=f, fill=renk, anchor="lm")
    return w


def satirlar(v):
    """Tablo satırları: (yükseklik, zemin, yazı rengi, kalın, punto, hücreler)"""
    s = []
    if v["yil"] and abs(v["devir"]) > 0.005:
        dv = v["devir"]
        s.append((44, ACIK_TURUNCU, KOYU, True, 19,
                  [f"01.01.{v['yil']}", f"{v['yil'] - 1} yılından devir", "", "", "",
                   para(dv) if dv > 0 else "", para(-dv) if dv < 0 else "", para(dv)]))
    for tur, tarih, tutar, aciklama, fis_no, kalemler, bakiye in v["islemler"]:
        if tur == "SATIŞ":
            baslik = f"Fiş No: {fis_no}" + (f"  ({aciklama})" if aciklama else "")
            s.append((44, "#FFF6EC", KOYU, True, 19,
                      [tarih_goster(tarih), baslik, "", "", "", para(tutar), "", para(bakiye)]))
            for urun, adet, fiyat in kalemler:
                s.append((36, None, "#555555", False, 17,
                          ["", "• " + urun, f"{adet:g}".replace(".", ","), para(fiyat),
                           para(adet * fiyat), "", "", ""]))
        else:
            s.append((44, None, YESIL, True, 19,
                      [tarih_goster(tarih), "Ödeme" + (f"  ({aciklama})" if aciklama else ""),
                       "", "", "", "", para(tutar), para(bakiye)]))
    if not s:
        s.append((50, None, GRI, False, 19, ["", "Kayıtlı işlem bulunmuyor.", "", "", "", "", "", ""]))
    return s


def _logo(boyut):
    try:
        im = Image.open(LOGO_PATH).convert("RGB")
        im.thumbnail((boyut, boyut), Image.LANCZOS)
        return im
    except OSError:
        return None


def _ilk_sayfa_basligi(im, d, v, sayfa, toplam):
    logo = _logo(160)
    if logo:
        im.paste(logo, (M, 40))
    yaz(d, M + 190, 95, FIRMA, 56, True, TURUNCU)
    yaz(d, M + 193, 160, "HESAP EKSTRESİ", 28, True, "#5A4A3A")
    yaz(d, W - M, 85, f"Tarih: {datetime.now():%d.%m.%Y}", 22, renk="#555555", hiza="r")
    yaz(d, W - M, 120, f"Sayfa {sayfa}/{toplam}", 19, renk="#999999", hiza="r")
    d.rectangle((M, 225, W - M, 231), fill=TURUNCU)

    d.rounded_rectangle((M, 255, W - M, 365), 16, fill=ACIK_TURUNCU)
    yaz(d, M + 24, 285, "SAYIN", 18, True, KOYU_TURUNCU)
    yaz(d, M + 24, 330, v["ad"], 32, True, KOYU, genislik=620)
    if v["tel"]:
        yaz(d, W - M - 24, 285, f"Tel: {v['tel']}", 20, renk="#555555", hiza="r")
    donem = (f"Dönem: {v['yil']} yılı (önceki yıllar devir)" if v["yil"]
             else "Dönem: Tüm işlemler")
    yaz(d, W - M - 24, 330, donem, 20, renk="#555555", hiza="r")

    kutular = [("Önceki Yıldan Devir", v["devir"])] if v["yil"] else []
    son = "Alacağınız" if v["bakiye"] < -0.005 else "KALAN BORÇ"
    kutular += [("Toplam Alışveriş", v["satis"]), ("Toplam Ödeme", v["tahsilat"]), (son, abs(v["bakiye"]))]
    bosluk = 16
    bw = (W - 2 * M - bosluk * (len(kutular) - 1)) / len(kutular)
    for i, (etiket, deger) in enumerate(kutular):
        x0 = M + i * (bw + bosluk)
        sonuncu = i == len(kutular) - 1
        d.rounded_rectangle((x0, 390, x0 + bw, 490), 14, fill=TURUNCU if sonuncu else "white",
                            outline=TURUNCU if sonuncu else "#E6D5C3", width=2)
        yaz(d, x0 + bw / 2, 420, etiket, 19, sonuncu, "white" if sonuncu else GRI, "c")
        yaz(d, x0 + bw / 2, 460, para(deger), 30, True, "white" if sonuncu else KOYU, "c", bw - 20)
    return 520


def _diger_sayfa_basligi(im, d, v, sayfa, toplam):
    logo = _logo(90)
    if logo:
        im.paste(logo, (M, 28))
    yaz(d, M + 110, 60, FIRMA, 34, True, TURUNCU)
    yaz(d, M + 111, 100, f"Hesap Ekstresi – {v['ad']}", 20, renk="#555555", genislik=700)
    yaz(d, W - M, 60, f"Sayfa {sayfa}/{toplam}", 19, renk="#999999", hiza="r")
    d.rectangle((M, 138, W - M, 143), fill=TURUNCU)
    return 165


def _tablo_basligi(d, y):
    d.rectangle((M, y, W - M, y + 46), fill=TURUNCU)
    x = M
    for baslik, genislik, hiza in KOLONLAR:
        yaz(d, x + genislik - 10 if hiza == "r" else x + 10, y + 23, baslik, 18, True, "white", hiza)
        x += genislik
    return y + 46


def _satir_ciz(d, y, satir):
    h, zemin, renk, kalin, boyut, hucreler = satir
    if zemin:
        d.rectangle((M, y, W - M, y + h), fill=zemin)
    x = M
    for i, (metin, (_, genislik, hiza)) in enumerate(zip(hucreler, KOLONLAR)):
        if metin:
            r = KOYU if i == len(KOLONLAR) - 1 else renk      # bakiye sütunu hep koyu
            yaz(d, x + genislik - 10 if hiza == "r" else x + 10, y + h / 2, metin, boyut,
                kalin, r, hiza, genislik - 16)
        x += genislik
    d.line((M, y + h, W - M, y + h), fill="#EDE3D9", width=1)
    return y + h


def sayfalar(v):
    """Ekstreyi A4 sayfalara çizer: [(sayfa görseli, içeriğin bittiği y), ...]"""
    tum = satirlar(v)
    sinir, alt_bilgi = H - 70, 190
    bolumler, mevcut, y = [], [], 520 + 46
    for s in tum:
        if y + s[0] > sinir:
            bolumler.append(mevcut)
            mevcut, y = [], 165 + 46
        mevcut.append(s)
        y += s[0]
    if y + alt_bilgi > sinir:                 # alt toplam sığmıyorsa yeni sayfaya
        bolumler.append(mevcut)
        mevcut = []
    bolumler.append(mevcut)

    sonuc = []
    for n, bolum in enumerate(bolumler, 1):
        im = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(im)
        baslik = _ilk_sayfa_basligi if n == 1 else _diger_sayfa_basligi
        y = baslik(im, d, v, n, len(bolumler))
        if bolum:
            y = _tablo_basligi(d, y)
            for s in bolum:
                y = _satir_ciz(d, y, s)
        if n == len(bolumler):
            y = _alt_bilgi(d, y + 14, v)
        sonuc.append((im, min(H, y + 40)))
    return sonuc


def _alt_bilgi(d, y, v):
    d.line((M, y, W - M, y), fill=TURUNCU, width=3)
    y += 48
    b = v["bakiye"]
    if b < -0.005:
        etiket = "ALACAK BAKİYENİZ:"
    elif v["yil"] and v["yil"] < datetime.now().year:
        etiket = f"{v['yil']} YILI SONU BORÇ BAKİYENİZ:"
    else:
        etiket = "GÜNCEL BORÇ BAKİYENİZ:"
    gen = yaz(d, W - M, y, para(abs(b)), 36, True, TURUNCU, "r")
    yaz(d, W - M - gen - 20, y, etiket, 22, True, KOYU, "r")
    y += 62
    yaz(d, M, y, f"Bu ekstre {datetime.now():%d.%m.%Y %H:%M} tarihinde oluşturulmuştur.", 17, renk="#999999")
    y += 32
    yaz(d, M, y, f"Bizi tercih ettiğiniz için teşekkür ederiz.  —  {FIRMA}", 18, True, KOYU_TURUNCU)
    return y + 20


def olustur(db, mid, yil=None):
    """PNG(ler) ve PDF dosyalarını oluşturur. Dönüş: (png yolları, pdf yolu, önizleme görselleri, veri)"""
    v = veri(db, mid, yil)
    os.makedirs(EKSTRE_KLASORU, exist_ok=True)
    ad = re.sub(r'[\\/:*?"<>|]', "", v["ad"]).strip().replace(" ", "_") or "musteri"
    taban = os.path.join(EKSTRE_KLASORU,
                         f"Ekstre_{ad}_{datetime.now():%Y-%m-%d}_{yil if yil else 'tum'}")
    sayfa_listesi = sayfalar(v)
    tam = [im for im, _ in sayfa_listesi]
    kirpik = [im.crop((0, 0, W, alt)) for im, alt in sayfa_listesi]
    pdf = taban + ".pdf"
    tam[0].save(pdf, "PDF", resolution=150.0, save_all=True, append_images=tam[1:])
    pngler = []
    for i, im in enumerate(kirpik, 1):
        yol = taban + (f"_s{i}" if len(kirpik) > 1 else "") + ".png"
        im.save(yol, optimize=True)
        pngler.append(yol)
    return pngler, pdf, kirpik, v


# ---------------------------------------------------------------- pano & whatsapp
def _ps(komut):
    subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", komut], check=True,
                   capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)


def _q(yol):
    return "'" + yol.replace("'", "''") + "'"


def gorseli_panoya_kopyala(yol):
    _ps("Add-Type -AssemblyName System.Windows.Forms, System.Drawing; "
        f"$i = [System.Drawing.Image]::FromFile({_q(yol)}); "
        "[System.Windows.Forms.Clipboard]::SetImage($i); $i.Dispose()")


def dosyalari_panoya_kopyala(yollar):
    _ps("Add-Type -AssemblyName System.Windows.Forms; "
        "$c = New-Object System.Collections.Specialized.StringCollection; "
        + "".join(f"[void]$c.Add({_q(y)}); " for y in yollar)
        + "[System.Windows.Forms.Clipboard]::SetFileDropList($c)")


def telefon_duzenle(tel):
    """0555 123 45 67 -> 905551234567"""
    n = re.sub(r"\D", "", tel or "")
    if n.startswith("00"):
        n = n[2:]
    if len(n) == 11 and n.startswith("0"):
        n = "90" + n[1:]
    elif len(n) == 10 and n.startswith("5"):
        n = "90" + n
    return n


def whatsapp_ac(tel, mesaj):
    no, metin = telefon_duzenle(tel), urllib.parse.quote(mesaj)
    try:                                      # masaüstü uygulaması kuruluysa doğrudan onu aç
        os.startfile(f"whatsapp://send?phone={no}&text={metin}" if no else f"whatsapp://send?text={metin}")
    except OSError:
        os.startfile(f"https://wa.me/{no}?text={metin}" if no else f"https://wa.me/?text={metin}")


# ---------------------------------------------------------------- pencere
class EkstrePenceresi(tk.Toplevel):
    def __init__(self, ana, db, mid, yil, degisti):
        super().__init__(ana)
        self.db, self.mid, self.yil, self.degisti = db, mid, yil, degisti
        self.title(f"Ekstre Gönder - {db.musteri(mid)[1]}")
        self.geometry("1000x760")
        self.minsize(900, 640)
        self.transient(ana)
        self.sayfa = 0

        # --- sol: önizleme
        sol = ttk.Frame(self, padding=10)
        sol.pack(side="left", fill="both", expand=True)
        self.onizleme = tk.Label(sol, bg="#EFE7DF", bd=0)
        self.onizleme.pack(fill="both", expand=True)
        self.onizleme.bind("<Configure>", lambda e: self.onizleme_ciz())
        gezinti = ttk.Frame(sol)
        gezinti.pack(fill="x", pady=(6, 0))
        self.onceki = ttk.Button(gezinti, text="◀", width=3, command=lambda: self.sayfa_degis(-1))
        self.onceki.pack(side="left")
        self.sayfa_lbl = ttk.Label(gezinti, text="")
        self.sayfa_lbl.pack(side="left", padx=8)
        self.sonraki = ttk.Button(gezinti, text="▶", width=3, command=lambda: self.sayfa_degis(1))
        self.sonraki.pack(side="left")

        # --- sağ: seçenekler
        sag = ttk.Frame(self, padding=(4, 10, 12, 10), width=370)
        sag.pack(side="right", fill="y")
        sag.pack_propagate(False)

        kapsam = ttk.LabelFrame(sag, text="Ekstrede Görünecekler", padding=10)
        kapsam.pack(fill="x")
        self.kapsam = tk.IntVar(value=0)
        ttk.Radiobutton(kapsam, text="Bugüne kadarki tüm işlemler", value=0, variable=self.kapsam,
                        command=self.olustur).pack(anchor="w")
        ttk.Radiobutton(kapsam, text=f"Sadece {yil} yılı (önceki yıllar devir)", value=yil,
                        variable=self.kapsam, command=self.olustur).pack(anchor="w", pady=(4, 0))

        wa = ttk.LabelFrame(sag, text="WhatsApp", padding=10)
        wa.pack(fill="x", pady=10)
        ttk.Label(wa, text="Telefon:").pack(anchor="w")
        self.tel = tk.StringVar(value=db.musteri(mid)[2])
        ttk.Entry(wa, textvariable=self.tel).pack(fill="x", pady=(2, 8))
        ttk.Label(wa, text="Mesaj:").pack(anchor="w")
        self.mesaj = tk.Text(wa, height=5, wrap="word", font=("Segoe UI", 10), relief="solid",
                             borderwidth=1)
        self.mesaj.pack(fill="x", pady=(2, 0))

        ttk.Button(sag, text="Görseli Kopyala + WhatsApp'ı Aç", style="Vurgu.TButton",
                   command=self.whatsapp).pack(fill="x", ipady=4)
        ttk.Button(sag, text="Görsel + PDF Dosyalarını Kopyala",
                   command=self.dosyalari_kopyala).pack(fill="x", pady=(8, 0))
        alt = ttk.Frame(sag)
        alt.pack(fill="x", pady=(8, 0))
        ttk.Button(alt, text="PDF'i Aç", command=lambda: os.startfile(self.pdf)).pack(
            side="left", expand=True, fill="x")
        ttk.Button(alt, text="Klasörde Göster", command=self.klasorde_goster).pack(
            side="left", expand=True, fill="x", padx=(6, 0))

        ttk.Label(sag, wraplength=340, justify="left", foreground="#6A5A4A", text=(
            "Nasıl gönderilir?\n"
            "1) 'Görseli Kopyala + WhatsApp'ı Aç'a basın. Müşterinin sohbeti açılır.\n"
            "2) Sohbette Ctrl+V yapıp görseli gönderin.\n"
            "3) PDF'i de göndermek için 'Görsel + PDF Dosyalarını Kopyala'ya basıp "
            "sohbette tekrar Ctrl+V yapın.")).pack(anchor="w", pady=(14, 0))
        self.durum = ttk.Label(sag, text="", foreground="#1b7f2a", wraplength=340)
        self.durum.pack(anchor="w", pady=(10, 0))

        self.olustur()
        self.focus_force()

    def olustur(self):
        try:
            self.pngler, self.pdf, self.gorseller, v = olustur(self.db, self.mid, self.kapsam.get() or None)
        except OSError as e:
            messagebox.showerror("Ekstre", f"Dosya oluşturulamadı:\n{e}", parent=self)
            return
        bakiye_metni = ("alacak bakiyeniz" if v["bakiye"] < -0.005 else
                        f"{v['yil']} yılı sonu borç bakiyeniz" if v["yil"] and v["yil"] < datetime.now().year
                        else "güncel borç bakiyeniz")
        self.mesaj.delete("1.0", "end")
        self.mesaj.insert("1.0", f"Sayın {v['ad']},\n{FIRMA} hesap ekstreniz ektedir.\n"
                                 f"{bakiye_metni[0].upper() + bakiye_metni[1:]}: {para(abs(v['bakiye']))}\n"
                                 "İyi günler dileriz.")
        self.sayfa = 0
        self.onizleme_ciz()
        self.durum.config(text=f"Hazır: {os.path.basename(self.pdf)}")

    def onizleme_ciz(self):
        if not getattr(self, "gorseller", None):
            return
        alan_w, alan_h = self.onizleme.winfo_width() - 20, self.onizleme.winfo_height() - 20
        if alan_w < 50 or alan_h < 50:
            return
        im = self.gorseller[self.sayfa].copy()
        im.thumbnail((alan_w, alan_h), Image.LANCZOS)
        self._foto = ImageTk.PhotoImage(im, master=self)
        self.onizleme.config(image=self._foto)
        n = len(self.gorseller)
        self.sayfa_lbl.config(text=f"Sayfa {self.sayfa + 1} / {n}")
        self.onceki.state(["!disabled" if self.sayfa > 0 else "disabled"])
        self.sonraki.state(["!disabled" if self.sayfa < n - 1 else "disabled"])

    def sayfa_degis(self, yon):
        self.sayfa = max(0, min(len(self.gorseller) - 1, self.sayfa + yon))
        self.onizleme_ciz()

    def telefonu_kaydet(self):
        """Telefon değiştirildiyse müşteri kartına da yaz."""
        _, ad, tel, notlar = self.db.musteri(self.mid)
        yeni = self.tel.get().strip()
        if yeni != tel:
            self.db.musteri_guncelle(self.mid, ad, yeni, notlar)
            self.degisti()

    def whatsapp(self):
        self.telefonu_kaydet()
        try:
            gorseli_panoya_kopyala(self.pngler[0])
        except (subprocess.SubprocessError, OSError) as e:
            messagebox.showerror("Pano", f"Görsel panoya kopyalanamadı:\n{e}", parent=self)
            return
        ek = f" (ekstre {len(self.pngler)} sayfa; diğer sayfalar için dosyaları kopyalayın)" \
            if len(self.pngler) > 1 else ""
        self.durum.config(text="Görsel kopyalandı. WhatsApp'ta sohbete Ctrl+V yapın." + ek)
        whatsapp_ac(self.tel.get(), self.mesaj.get("1.0", "end").strip())

    def dosyalari_kopyala(self):
        try:
            dosyalari_panoya_kopyala(self.pngler + [self.pdf])
        except (subprocess.SubprocessError, OSError) as e:
            messagebox.showerror("Pano", f"Dosyalar panoya kopyalanamadı:\n{e}", parent=self)
            return
        self.durum.config(text="Görsel ve PDF kopyalandı. WhatsApp sohbetinde Ctrl+V yapın.")

    def klasorde_goster(self):
        subprocess.Popen(["explorer", "/select,", os.path.normpath(self.pdf)])
