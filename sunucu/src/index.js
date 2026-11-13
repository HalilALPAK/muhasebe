/**
 * Oğul Tarım Muhasebe - eşitleme sunucusu (Cloudflare Workers + D1).
 *
 * Laptop programı ve telefon uygulaması kendi kayıtlarını yerelde tutar; internet olduğunda
 * değişenleri buraya gönderir ve diğer cihazın değişikliklerini alır. Birleştirme kuralları
 * yalnızca burada çalışır:
 *   - Aynı kayıt iki cihazda değiştiyse son değişiklik (guncelleme zamanı) kazanır.
 *   - Silme de bir değişikliktir; kayıt silindi=1 olarak saklanır, eski kopyadan geri gelmez.
 *   - Aynı isimle açılan iki müşteri birleşir (esleme tablosu).
 *   - Fiş numarası çakışırsa önce gelen korunur, sonraki sıradaki boş numarayı alır.
 *   - Silinmiş müşteriye daha sonra işlem girildiyse müşteri geri gelir (veri kaybolmaz).
 */

const API = 1;
const SAYFA = 1000; // bir cevapta en fazla bu kadar kayıt döner
const EN_FAZLA_GELEN = 2000; // bir istekte en fazla bu kadar kayıt gönderilebilir

class GirdiHatasi extends Error {}

const json = (veri, kod = 200) =>
  new Response(JSON.stringify(veri), { status: kod, headers: { 'Content-Type': 'application/json; charset=utf-8' } });

const kucuk = (s) => s.replaceAll('I', 'ı').replaceAll('İ', 'i').toLowerCase().trim();

async function yetkili(istek, env) {
  const beklenen = env.API_ANAHTARI;
  const gelen = (istek.headers.get('Authorization') || '').replace(/^Bearer\s+/i, '');
  if (!beklenen || !gelen) return false;
  const a = new TextEncoder().encode(gelen);
  const b = new TextEncoder().encode(beklenen);
  if (a.byteLength !== b.byteLength) return false;
  return crypto.subtle.timingSafeEqual(a, b);
}

// ---------------------------------------------------------------- doğrulama
const sayi = (v) => {
  if (typeof v !== 'number' || !Number.isFinite(v)) throw new GirdiHatasi(`geçersiz sayı: ${v}`);
  return v;
};
const zaman = (v) => {
  if (!Number.isInteger(v) || v < 0) throw new GirdiHatasi(`geçersiz zaman: ${v}`);
  return v;
};
const tarih = (v) => {
  if (typeof v !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(v)) throw new GirdiHatasi(`geçersiz tarih: ${v}`);
  return v;
};
const metin = (v, en = 2000) => {
  if (v == null) return '';
  if (typeof v !== 'string' || v.length > en) throw new GirdiHatasi('geçersiz metin');
  return v;
};
const kimlik = (v) => {
  if (typeof v !== 'string' || !/^[A-Za-z0-9_-]{8,64}$/.test(v)) throw new GirdiHatasi(`geçersiz kimlik: ${v}`);
  return v;
};

function dogrula(g) {
  if (!g || typeof g !== 'object' || g.api !== API) {
    throw new GirdiHatasi('Uygulama ve sunucu sürümleri uyumsuz. Programı ve uygulamayı güncelleyin.');
  }
  const d = g.degisiklikler || {};
  const musteri = (d.musteri || []).map((m) => ({
    uuid: kimlik(m.uuid), ad: metin(m.ad, 300).trim(), telefon: metin(m.telefon, 100), notlar: metin(m.notlar), guncelleme: zaman(m.guncelleme),
  }));
  if (musteri.some((m) => !m.ad)) throw new GirdiHatasi('adı boş müşteri');
  const islem = (d.islem || []).map((i) => {
    if (i.tur !== 'SATIŞ' && i.tur !== 'TAHSİLAT') throw new GirdiHatasi(`geçersiz işlem türü: ${i.tur}`);
    if (i.fis_no != null && (!Number.isInteger(i.fis_no) || i.fis_no < 0)) throw new GirdiHatasi(`geçersiz fiş no: ${i.fis_no}`);
    const kalemler = (i.kalemler || []).map((k) => ({ urun: metin(k.urun, 300), adet: sayi(k.adet), birim_fiyat: sayi(k.birim_fiyat) }));
    return {
      uuid: kimlik(i.uuid), musteri_uuid: kimlik(i.musteri_uuid), tur: i.tur, tarih: tarih(i.tarih), tutar: sayi(i.tutar),
      aciklama: metin(i.aciklama), fis_no: i.fis_no ?? null, kalemler, guncelleme: zaman(i.guncelleme),
    };
  });
  const gider = (d.gider || []).map((x) => ({
    uuid: kimlik(x.uuid), tarih: tarih(x.tarih), kategori: metin(x.kategori, 200), tutar: sayi(x.tutar), aciklama: metin(x.aciklama), guncelleme: zaman(x.guncelleme),
  }));
  const silinen = (d.silinen || []).map((s) => {
    if (!['musteri', 'islem', 'gider'].includes(s.tablo)) throw new GirdiHatasi(`geçersiz tablo: ${s.tablo}`);
    return { uuid: kimlik(s.uuid), tablo: s.tablo, zaman: zaman(s.zaman) };
  });
  if (musteri.length + islem.length + gider.length + silinen.length > EN_FAZLA_GELEN) {
    throw new GirdiHatasi(`bir seferde en fazla ${EN_FAZLA_GELEN} kayıt gönderilebilir`);
  }
  const sonSurum = Number.isInteger(g.son_surum) && g.son_surum >= 0 ? g.son_surum : 0;
  return { cihaz: metin(g.cihaz, 100), sonSurum, musteri, islem, gider, silinen };
}

// ---------------------------------------------------------------- toplu SQL (az sorgu: D1 ücretsiz planda istek başına 50)
const jsonSatir = (alanlar) => alanlar.map((a) => `json_extract(value, '$.${a}')`).join(', ');

function silmeSorgulari(db, tablo, liste) {
  if (!liste.length) return [];
  const p = JSON.stringify(liste.map((s) => ({ uuid: s.uuid, zaman: s.zaman })));
  const kosul = tablo === 'musteri'
    ? 'AND NOT EXISTS (SELECT 1 FROM islem i WHERE i.musteri_uuid = musteri.uuid AND i.silindi = 0)' // işlemi olan müşteri silinmez
    : '';
  return [
    db.prepare(`UPDATE ${tablo} SET silindi = 1, guncelleme = t.z
                FROM (SELECT json_extract(value, '$.uuid') u, json_extract(value, '$.zaman') z FROM json_each(?1)) t
                WHERE ${tablo}.uuid = t.u AND ${tablo}.silindi = 0 AND ${tablo}.guncelleme <= t.z ${kosul}`).bind(p),
    // hiç görülmemiş kayıt silindiyse izi saklanır; eski kopyası sonradan gelirse geri gelmez
    db.prepare(`INSERT INTO ${tablo} (uuid, guncelleme, silindi)
                SELECT json_extract(value, '$.uuid'), json_extract(value, '$.zaman'), 1 FROM json_each(?1) WHERE true
                ON CONFLICT(uuid) DO NOTHING`).bind(p),
  ];
}

// ---------------------------------------------------------------- eşitleme
async function esitle(env, govde) {
  const g = dogrula(govde);
  const db = env.DB;
  const rapor = { yeni_musteri: 0, birlesen_musteri: 0, guncellenen_musteri: 0, yeni_islem: 0, guncellenen_islem: 0, silinen: 0, yeni_gider: 0, fis_degisen: [] };

  const sunucuSurum = (await db.prepare("SELECT deger FROM meta WHERE anahtar = 'surum'").first('deger')) ?? 0;
  if (g.sonSurum > sunucuSurum) return { api: API, sunucu_sifirlandi: true }; // sunucu verisi sıfırlanmış: cihaz her şeyi yeniden gönderir

  const islemIdleri = JSON.stringify([...g.islem.map((i) => i.uuid), ...g.silinen.filter((s) => s.tablo === 'islem').map((s) => s.uuid)]);
  const giderIdleri = JSON.stringify(g.gider.map((x) => x.uuid));
  const [eslemeR, musteriR, islemR, giderR, fisR, enBuyukR] = await db.batch([
    db.prepare('SELECT eski, yeni FROM esleme'),
    db.prepare('SELECT uuid, ad, telefon, notlar, guncelleme, silindi FROM musteri'),
    db.prepare('SELECT uuid, guncelleme, silindi FROM islem WHERE uuid IN (SELECT value FROM json_each(?1))').bind(islemIdleri),
    db.prepare('SELECT uuid, guncelleme FROM gider WHERE uuid IN (SELECT value FROM json_each(?1))').bind(giderIdleri),
    db.prepare('SELECT fis_no, uuid FROM islem WHERE silindi = 0 AND fis_no IS NOT NULL'),
    db.prepare('SELECT COALESCE(MAX(fis_no), 0) m FROM islem'),
  ]);

  const esleme = new Map(eslemeR.results.map((r) => [r.eski, r.yeni]));
  const cozumle = (u) => {
    for (let n = 0; n < 10 && esleme.has(u); n++) u = esleme.get(u);
    return u;
  };
  const musteriler = new Map(musteriR.results.map((r) => [r.uuid, r]));
  const adla = new Map();
  for (const m of musteriR.results) if (!m.silindi && m.ad && !adla.has(kucuk(m.ad))) adla.set(kucuk(m.ad), m.uuid);
  const mevcutIslem = new Map(islemR.results.map((r) => [r.uuid, r]));
  const mevcutGider = new Map(giderR.results.map((r) => [r.uuid, r]));
  const fisSahibi = new Map(fisR.results.map((r) => [r.fis_no, r.uuid]));
  const fisNumarasi = new Map(fisR.results.map((r) => [r.uuid, r.fis_no]));
  let enBuyukFis = enBuyukR.results[0].m;

  for (const s of g.silinen) {
    const r = s.tablo === 'islem' ? mevcutIslem.get(s.uuid) : s.tablo === 'musteri' ? musteriler.get(s.uuid) : null;
    if (r && !r.silindi && r.guncelleme <= s.zaman) rapor.silinen++;
  }

  // müşteriler: yeni olanlar aynı isimli canlı müşteriyle birleşir
  const musteriYaz = [], yeniEsleme = [], doldur = [];
  for (const m of g.musteri) {
    const mevcut = musteriler.get(m.uuid);
    if (mevcut) {
      if (m.guncelleme > mevcut.guncelleme) {
        musteriYaz.push(m);
        rapor.guncellenen_musteri++;
        mevcut.silindi = 0;
      }
      continue;
    }
    if (esleme.has(m.uuid)) continue; // daha önce birleştirilmiş
    const hedef = adla.get(kucuk(m.ad));
    if (hedef) {
      esleme.set(m.uuid, hedef);
      yeniEsleme.push({ eski: m.uuid, yeni: hedef });
      doldur.push({ uuid: hedef, telefon: m.telefon, notlar: m.notlar });
      rapor.birlesen_musteri++;
    } else {
      musteriYaz.push(m);
      musteriler.set(m.uuid, { ...m, silindi: 0 });
      adla.set(kucuk(m.ad), m.uuid);
      rapor.yeni_musteri++;
    }
  }

  // işlemler
  const islemYaz = [], canlandir = new Set();
  for (const i of g.islem) {
    const mevcut = mevcutIslem.get(i.uuid);
    if (mevcut && i.guncelleme <= mevcut.guncelleme) continue;
    const mu = cozumle(i.musteri_uuid);
    const musteri = musteriler.get(mu);
    if (!musteri) throw new GirdiHatasi('işlemin müşterisi bulunamadı');
    if (musteri.silindi) {
      canlandir.add(mu); // silinmiş müşteriye sonradan işlem girilmiş: müşteri geri gelir
      musteri.silindi = 0;
    }
    let fis = null;
    if (i.tur === 'SATIŞ') {
      fis = i.fis_no;
      const sahip = fis ? fisSahibi.get(fis) : undefined;
      if (!fis || (sahip && sahip !== i.uuid)) {
        const yeni = ++enBuyukFis;
        if (fis) rapor.fis_degisen.push({ eski: fis, yeni, uuid: i.uuid });
        fis = yeni;
      }
      const eski = fisNumarasi.get(i.uuid);
      if (eski != null && eski !== fis) fisSahibi.delete(eski);
      fisSahibi.set(fis, i.uuid);
      fisNumarasi.set(i.uuid, fis);
      enBuyukFis = Math.max(enBuyukFis, fis);
    }
    islemYaz.push({ ...i, musteri_uuid: mu, fis_no: fis, kalemler: JSON.stringify(i.kalemler) });
    if (mevcut) rapor.guncellenen_islem++;
    else rapor.yeni_islem++;
  }

  const giderYaz = g.gider.filter((x) => {
    const m = mevcutGider.get(x.uuid);
    if (!m) rapor.yeni_gider++;
    return !m || x.guncelleme > m.guncelleme;
  });

  const yaz = [
    ...silmeSorgulari(db, 'islem', g.silinen.filter((s) => s.tablo === 'islem')),
    ...silmeSorgulari(db, 'gider', g.silinen.filter((s) => s.tablo === 'gider')),
  ];
  if (musteriYaz.length) {
    yaz.push(db.prepare(`INSERT INTO musteri (uuid, ad, telefon, notlar, guncelleme, silindi)
        SELECT ${jsonSatir(['uuid', 'ad', 'telefon', 'notlar', 'guncelleme'])}, 0 FROM json_each(?1) WHERE true
        ON CONFLICT(uuid) DO UPDATE SET ad = excluded.ad, telefon = excluded.telefon, notlar = excluded.notlar,
          guncelleme = excluded.guncelleme, silindi = 0
        WHERE excluded.guncelleme > musteri.guncelleme`).bind(JSON.stringify(musteriYaz)));
  }
  if (yeniEsleme.length) {
    yaz.push(db.prepare(`INSERT OR REPLACE INTO esleme (eski, yeni) SELECT ${jsonSatir(['eski', 'yeni'])} FROM json_each(?1)`)
      .bind(JSON.stringify(yeniEsleme)));
    yaz.push(db.prepare(`UPDATE musteri SET
          telefon = CASE WHEN musteri.telefon = '' THEN t.tel ELSE musteri.telefon END,
          notlar = CASE WHEN musteri.notlar = '' THEN t.n ELSE musteri.notlar END,
          guncelleme = musteri.guncelleme + 1
        FROM (SELECT json_extract(value, '$.uuid') u, json_extract(value, '$.telefon') tel, json_extract(value, '$.notlar') n FROM json_each(?1)) t
        WHERE musteri.uuid = t.u AND ((musteri.telefon = '' AND t.tel <> '') OR (musteri.notlar = '' AND t.n <> ''))`)
      .bind(JSON.stringify(doldur)));
  }
  if (canlandir.size) {
    yaz.push(db.prepare('UPDATE musteri SET silindi = 0, guncelleme = guncelleme + 1 WHERE silindi = 1 AND uuid IN (SELECT value FROM json_each(?1))')
      .bind(JSON.stringify([...canlandir])));
  }
  if (islemYaz.length) {
    yaz.push(db.prepare(`INSERT INTO islem (uuid, musteri_uuid, tur, tarih, tutar, aciklama, fis_no, kalemler, guncelleme, silindi)
        SELECT ${jsonSatir(['uuid', 'musteri_uuid', 'tur', 'tarih', 'tutar', 'aciklama', 'fis_no', 'kalemler', 'guncelleme'])}, 0
        FROM json_each(?1) WHERE true
        ON CONFLICT(uuid) DO UPDATE SET musteri_uuid = excluded.musteri_uuid, tur = excluded.tur, tarih = excluded.tarih,
          tutar = excluded.tutar, aciklama = excluded.aciklama, fis_no = excluded.fis_no, kalemler = excluded.kalemler,
          guncelleme = excluded.guncelleme, silindi = 0
        WHERE excluded.guncelleme > islem.guncelleme`).bind(JSON.stringify(islemYaz)));
  }
  yaz.push(...silmeSorgulari(db, 'musteri', g.silinen.filter((s) => s.tablo === 'musteri')));
  if (giderYaz.length) {
    yaz.push(db.prepare(`INSERT INTO gider (uuid, tarih, kategori, tutar, aciklama, guncelleme, silindi)
        SELECT ${jsonSatir(['uuid', 'tarih', 'kategori', 'tutar', 'aciklama', 'guncelleme'])}, 0 FROM json_each(?1) WHERE true
        ON CONFLICT(uuid) DO UPDATE SET tarih = excluded.tarih, kategori = excluded.kategori, tutar = excluded.tutar,
          aciklama = excluded.aciklama, guncelleme = excluded.guncelleme, silindi = 0
        WHERE excluded.guncelleme > gider.guncelleme`).bind(JSON.stringify(giderYaz)));
  }
  const gelen = g.musteri.length + g.islem.length + g.gider.length + g.silinen.length;
  if (yaz.length) {
    yaz.push(db.prepare('INSERT INTO kayit (zaman, cihaz, gelen, rapor) VALUES (?1, ?2, ?3, ?4)')
      .bind(Date.now(), g.cihaz, gelen, JSON.stringify(rapor)));
    await db.batch(yaz); // tek işlem: ya hepsi yazılır ya hiçbiri
  }

  return { api: API, rapor, ...(await degisenler(db, g.sonSurum)) };
}

/** Cihazın son gördüğü sürümden sonra değişen kayıtlar (sayfa sayfa). */
async function degisenler(db, sonSurum) {
  const r = await db.prepare(`
    SELECT 'musteri' t, surum, json_object('uuid', uuid, 'ad', ad, 'telefon', telefon, 'notlar', notlar,
           'guncelleme', guncelleme, 'silindi', silindi) j FROM musteri WHERE surum > ?1
    UNION ALL
    SELECT 'islem', surum, json_object('uuid', uuid, 'musteri_uuid', musteri_uuid, 'tur', tur, 'tarih', tarih, 'tutar', tutar,
           'aciklama', aciklama, 'fis_no', fis_no, 'kalemler', json(kalemler), 'guncelleme', guncelleme, 'silindi', silindi) FROM islem WHERE surum > ?1
    UNION ALL
    SELECT 'gider', surum, json_object('uuid', uuid, 'tarih', tarih, 'kategori', kategori, 'tutar', tutar, 'aciklama', aciklama,
           'guncelleme', guncelleme, 'silindi', silindi) FROM gider WHERE surum > ?1
    ORDER BY surum LIMIT ?2`).bind(sonSurum, SAYFA + 1).all();
  const satirlar = r.results.slice(0, SAYFA);
  const cevap = { musteri: [], islem: [], gider: [] };
  for (const s of satirlar) cevap[s.t].push(JSON.parse(s.j));

  // sayfadaki işlemlerin müşterileri bu sayfada yoksa onlar da eklenir (cihazda eksik kalmasın)
  const sayfadaki = new Set(cevap.musteri.map((m) => m.uuid));
  const eksik = [...new Set(cevap.islem.map((i) => i.musteri_uuid))].filter((u) => !sayfadaki.has(u));
  const ekler = [db.prepare('SELECT eski, yeni FROM esleme')];
  if (eksik.length) {
    ekler.push(db.prepare(`SELECT uuid, ad, telefon, notlar, guncelleme, silindi FROM musteri WHERE uuid IN (SELECT value FROM json_each(?1))`)
      .bind(JSON.stringify(eksik)));
  }
  const [eslemeR, bagliR] = await db.batch(ekler);
  return {
    son_surum: satirlar.length ? satirlar[satirlar.length - 1].surum : sonSurum,
    daha_var: r.results.length > SAYFA,
    ...cevap,
    bagli_musteri: bagliR ? bagliR.results : [],
    esleme: eslemeR.results,
  };
}

async function durum(env) {
  const [s, m, i, g, k] = await env.DB.batch([
    env.DB.prepare("SELECT deger FROM meta WHERE anahtar = 'surum'"),
    env.DB.prepare('SELECT COUNT(*) n FROM musteri WHERE silindi = 0'),
    env.DB.prepare('SELECT COUNT(*) n FROM islem WHERE silindi = 0'),
    env.DB.prepare('SELECT COUNT(*) n FROM gider WHERE silindi = 0'),
    env.DB.prepare('SELECT zaman, cihaz FROM kayit ORDER BY id DESC LIMIT 1'),
  ]);
  return {
    uygulama: 'ogul_tarim', api: API, son_surum: s.results[0]?.deger ?? 0,
    musteri: m.results[0].n, islem: i.results[0].n, gider: g.results[0].n, son_esitleme: k.results[0] ?? null,
  };
}

/** Yedek: silinmemiş tüm kayıtlar. */
async function disaAktar(env) {
  const [m, i, g] = await env.DB.batch([
    env.DB.prepare('SELECT uuid, ad, telefon, notlar, guncelleme FROM musteri WHERE silindi = 0 ORDER BY ad'),
    env.DB.prepare('SELECT uuid, musteri_uuid, tur, tarih, tutar, aciklama, fis_no, kalemler, guncelleme FROM islem WHERE silindi = 0 ORDER BY tarih, fis_no'),
    env.DB.prepare('SELECT uuid, tarih, kategori, tutar, aciklama, guncelleme FROM gider WHERE silindi = 0 ORDER BY tarih'),
  ]);
  return {
    olusturma: new Date().toISOString(),
    musteri: m.results,
    islem: i.results.map((x) => ({ ...x, kalemler: JSON.parse(x.kalemler) })),
    gider: g.results,
  };
}

export default {
  async fetch(istek, env) {
    const { pathname } = new URL(istek.url);
    try {
      if (pathname === '/') return json({ uygulama: 'ogul_tarim', api: API });
      if (!(await yetkili(istek, env))) return json({ hata: 'Sunucu anahtarı hatalı.' }, 401);
      if (pathname === '/v1/durum' && istek.method === 'GET') return json(await durum(env));
      if (pathname === '/v1/esitle' && istek.method === 'POST') {
        let govde;
        try {
          govde = await istek.json();
        } catch {
          return json({ hata: 'geçersiz JSON' }, 400);
        }
        return json(await esitle(env, govde));
      }
      if (pathname === '/v1/disa-aktar' && istek.method === 'GET') return json(await disaAktar(env));
      return json({ hata: 'bulunamadı' }, 404);
    } catch (e) {
      if (e instanceof GirdiHatasi) return json({ hata: e.message }, 400);
      if (/UNIQUE constraint failed/.test(String(e))) {
        return json({ hata: 'Aynı anda başka bir cihaz eşitleme yaptı, tekrar deneyin.' }, 409);
      }
      return json({ hata: `Sunucu hatası: ${e.message}` }, 500);
    }
  },
};
