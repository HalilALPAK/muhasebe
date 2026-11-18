// Sunucuyu Cloudflare'e tek seferde kurar ve yayınlar.
//   1) Cloudflare girişi (tarayıcıda "Allow")   2) D1 veritabanı   3) şema
//   4) sunucuyu yayınlama                         5) rastgele anahtar   6) bağlantı testi
// Sonunda adres ve anahtar ekrana ve BAGLANTI_BILGILERI.txt dosyasına yazılır (depoya girmez).
import { spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

const AD = 'ogul-tarim-muhasebe';
const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';

function calistir(argumanlar, { yakala = false, girdi } = {}) {
  const r = spawnSync(npx, ['wrangler', ...argumanlar], {
    encoding: 'utf8', shell: process.platform === 'win32', input: girdi,
    stdio: yakala || girdi ? ['pipe', 'pipe', 'pipe'] : 'inherit',
  });
  return { kod: r.status, cikti: `${r.stdout || ''}${r.stderr || ''}` };
}

function dur(mesaj) {
  console.error(`\nHATA: ${mesaj}`);
  process.exit(1);
}

console.log('1/6 Cloudflare hesabı kontrol ediliyor...');
if (!/You are logged in|associated with the email/i.test(calistir(['whoami'], { yakala: true }).cikti)) {
  console.log('    Tarayıcıda Cloudflare sayfası açılacak: giriş yapıp "Allow" düğmesine basın.');
  if (calistir(['login']).kod !== 0) dur('Cloudflare girişi yapılamadı.');
}

console.log('2/6 Veritabanı (D1) hazırlanıyor...');
let toml = readFileSync('wrangler.toml', 'utf8');
let id = toml.match(/database_id = "([0-9a-f-]{36})"/)?.[1];
if (!id || /^0{8}-/.test(id)) {
  const olustur = calistir(['d1', 'create', AD], { yakala: true });
  id = olustur.cikti.match(/database_id\s*=\s*"([0-9a-f-]{36})"/)?.[1]
    || olustur.cikti.match(/"database_id":\s*"([0-9a-f-]{36})"/)?.[1];
  if (!id) { // daha önce oluşturulmuşsa listeden bul
    const liste = calistir(['d1', 'list', '--json'], { yakala: true }).cikti;
    try {
      id = JSON.parse(liste.slice(liste.indexOf('['))).find((d) => d.name === AD)?.uuid;
    } catch { /* aşağıda hata verilir */ }
  }
  if (!id) dur(`Veritabanı oluşturulamadı:\n${olustur.cikti}`);
  toml = toml.replace(/database_id = "[^"]*"/, `database_id = "${id}"`);
  writeFileSync('wrangler.toml', toml);
}
console.log(`    database_id = ${id}`);

console.log('3/6 Tablolar oluşturuluyor ve göçler uygulanıyor...');
if (calistir(['d1', 'execute', AD, '--remote', '--file', 'schema.sql', '-y']).kod !== 0) dur('Şema yüklenemedi.');
// göçler (goc/NNN_*.sql) sırayla ve bir kez: uygulanan son numara meta tablosunda 'goc' satırında
const gocCikti = calistir(['d1', 'execute', AD, '--remote', '--json', '--command', "SELECT deger FROM meta WHERE anahtar = 'goc'"], { yakala: true }).cikti;
let uygulanan = 0;
try {
  uygulanan = JSON.parse(gocCikti.slice(gocCikti.indexOf('[')))[0]?.results?.[0]?.deger ?? 0;
} catch { dur(`Göç durumu okunamadı:\n${gocCikti}`); }
for (const dosya of readdirSync('goc').filter((d) => /^\d{3}_.+\.sql$/.test(d)).sort()) {
  if (Number(dosya.slice(0, 3)) <= uygulanan) continue;
  console.log(`    göç: ${dosya}`);
  if (calistir(['d1', 'execute', AD, '--remote', '--file', join('goc', dosya), '-y']).kod !== 0) dur(`Göç uygulanamadı: ${dosya}`);
}

console.log('4/6 Sunucu yayınlanıyor...');
if (calistir(['deploy']).kod !== 0) dur('Yayınlanamadı.');

console.log('5/6 Sunucu anahtarı oluşturuluyor...');
const dosya = 'BAGLANTI_BILGILERI.txt';
const eski = existsSync(dosya) ? readFileSync(dosya, 'utf8').match(/Anahtar\s*:\s*(\S+)/)?.[1] : null;
const anahtar = eski || randomBytes(18).toString('base64url');
const gizli = calistir(['secret', 'put', 'API_ANAHTARI'], { girdi: `${anahtar}\n` });
if (gizli.kod !== 0) dur(`Anahtar kaydedilemedi:\n${gizli.cikti}`);

console.log('6/6 Adres bulunuyor ve test ediliyor...');
let adres = null;
try {
  const yapilandirma = readFileSync(join(process.env.APPDATA || join(homedir(), '.config'), 'xdg.config', '.wrangler', 'config', 'default.toml'), 'utf8');
  const jeton = yapilandirma.match(/oauth_token = "([^"]+)"/)?.[1];
  const api = (yol) => fetch(`https://api.cloudflare.com/client/v4${yol}`, { headers: { Authorization: `Bearer ${jeton}` } }).then((r) => r.json());
  const hesap = (await api('/accounts')).result[0].id;
  const alt = (await api(`/accounts/${hesap}/workers/subdomain`)).result.subdomain;
  adres = `https://${AD}.${alt}.workers.dev`;
} catch { /* adres bulunamazsa kullanıcı yukarıdaki çıktıdan alır */ }

let durum = 'test edilemedi';
if (adres) {
  for (let i = 0; i < 10; i++) {
    try {
      const d = await fetch(`${adres}/v1/durum`, { headers: { Authorization: `Bearer ${anahtar}` } }).then((r) => r.json());
      if (d.uygulama === 'ogul_tarim') { durum = `çalışıyor (${d.musteri} müşteri, ${d.islem} işlem)`; break; }
    } catch { /* yayın birkaç saniye sürebilir */ }
    await new Promise((s) => setTimeout(s, 3000));
  }
}

const bilgi = `Oğul Tarım Muhasebe - Sunucu bağlantı bilgileri
Bu dosyayı kimseyle paylaşmayın. Depoya gönderilmez.

Adres  : ${adres || '(yukarıdaki "deploy" çıktısındaki https://... .workers.dev adresi)'}
Anahtar: ${anahtar}
Durum  : ${durum}

Programda "Sunucu" düğmesine, telefonda ana ekrandaki "Sunucu" düğmesine basıp
bu adresi ve anahtarı girin.
`;
writeFileSync(dosya, bilgi);
console.log(`\n${'='.repeat(60)}\n${bilgi}${'='.repeat(60)}\nBu bilgiler ${join(process.cwd(), dosya)} dosyasına da yazıldı.`);
