#!/usr/bin/env node
/* ═══════════════════════════════════════════════════════════════
   暦エンジン回帰テスト
   ───────────────────────────────────────────────────────────────
   index.html に埋め込まれた天文暦エンジン(ALM)と吉日エンジン(KICHI)を
   切り出して実行し、外部の正解データと突き合わせる。

     ① calendar.json（ajnet.ne.jp 実測）の全日と
        六曜・旧暦（閏月含む）・月齢が一致すること
     ② 公開暦で確定している閏月の年が一致すること
     ③ 2026年の 天赦日 / 鬼宿日 / 一粒万倍日 が公開暦と一致すること

   実行:  node test_almanac.mjs
   終了コード 0 = 全件パス / 1 = 不一致あり
   ═══════════════════════════════════════════════════════════════ */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const ROOT = dirname(fileURLToPath(import.meta.url));

// ── index.html から暦エンジン部分だけを切り出す ──
const html = readFileSync(join(ROOT, 'index.html'), 'utf8');
const HEAD = 'var ALM_SYNODIC=';
const TAIL = 'function getKichijitsu(date){ return KICHI.ofDate(date); }';
const a = html.indexOf(HEAD);
const b = html.indexOf(TAIL);
if (a < 0 || b < 0) {
  console.error('❌ index.html から暦エンジンを切り出せません（ALM / KICHI の定義が見当たりません）');
  process.exit(1);
}
const engine = html.slice(a, b + TAIL.length);
const ctx = vm.createContext({ Math, Date, Map, JSON, console });
vm.runInContext(engine + '\nthis.ALM=ALM; this.KICHI=KICHI;', ctx);
const { ALM, KICHI } = ctx;

const dayNum = (y, m, d) => Math.floor(Date.UTC(y, m - 1, d) / 86400000);
let failures = 0;
const check = (ok, label, detail) => {
  if (ok) { console.log('  ✅ ' + label); }
  else { failures++; console.log('  ❌ ' + label + (detail ? '\n     ' + detail : '')); }
};

// ── ① calendar.json との突き合わせ ────────────────────────────
console.log('① calendar.json（実測暦）との一致');
const cal = JSON.parse(readFileSync(join(ROOT, 'calendar.json'), 'utf8'));
const keys = Object.keys(cal.days).sort();
const bad = { rokuyo: [], lunar: [], moon: [] };
for (const k of keys) {
  const [y, m, d] = k.split('-').map(Number);
  const n = dayNum(y, m, d);
  const e = cal.days[k];
  const l = ALM.lunisolar(n);
  const lunar = (l.leap ? '閏' : '') + l.month + '/' + l.day;
  if (ALM.rokuyo(n) !== e.rokuyo) bad.rokuyo.push(`${k}: ${ALM.rokuyo(n)} ≠ ${e.rokuyo}`);
  if (lunar !== e.lunar) bad.lunar.push(`${k}: ${lunar} ≠ ${e.lunar}`);
  if (Math.abs(ALM.moonAge(n) - e.moonAge) > 0.15) bad.moon.push(`${k}: ${ALM.moonAge(n)} ≠ ${e.moonAge}`);
}
check(bad.rokuyo.length === 0, `六曜 ${keys.length}日`, bad.rokuyo.slice(0, 5).join(' / '));
check(bad.lunar.length === 0, `旧暦 ${keys.length}日`, bad.lunar.slice(0, 5).join(' / '));
check(bad.moon.length === 0, `月齢 ${keys.length}日`, bad.moon.slice(0, 5).join(' / '));

// ── ② 閏月（公開暦で確定している年）────────────────────────────
console.log('② 旧暦の閏月');
const LEAPS = { 2014: '閏9', 2017: '閏5', 2020: '閏4', 2023: '閏2', 2025: '閏6', 2028: '閏5', 2031: '閏3' };
for (const [y, want] of Object.entries(LEAPS)) {
  const found = new Set();
  for (let m = 1; m <= 12; m++) {
    const dim = new Date(Date.UTC(+y, m, 0)).getUTCDate();
    for (let d = 1; d <= dim; d++) {
      const l = ALM.lunisolar(dayNum(+y, m, d));
      if (l.leap) found.add('閏' + l.month);
    }
  }
  const got = [...found].join(',') || 'なし';
  check(got === want, `${y}年 → ${want}`, got !== want ? `実際: ${got}` : '');
}

// ── ③ 2026年の吉日（公開暦との一致）──────────────────────────
console.log('③ 2026年の吉日');
const collect = (year, name) => {
  const out = [];
  for (let m = 1; m <= 12; m++) {
    const dim = new Date(Date.UTC(year, m, 0)).getUTCDate();
    for (let d = 1; d <= dim; d++) {
      if (KICHI.ofDayNum(dayNum(year, m, d)).names.includes(name)) out.push(`${m}/${d}`);
    }
  }
  return out;
};
const tensha = collect(2026, '天赦日').join(' ');
check(tensha === '3/5 5/4 5/20 7/19 10/1 12/16', '天赦日 6日', tensha);

const kishuku = collect(2026, '鬼宿日').join(' ');
check(kishuku === '1/2 1/30 2/27 3/27 4/24 5/22 6/19 7/17 8/14 9/11 10/9 11/6 12/4',
  '鬼宿日 13日（28日周期）', kishuku);

const ichiryu = collect(2026, '一粒万倍日');
check(ichiryu.length === 64, '一粒万倍日 年間64日', `実際: ${ichiryu.length}日`);
check(ichiryu.slice(0, 17).join(' ') === '1/1 1/2 1/5 1/14 1/17 1/26 1/29 2/8 2/13 2/20 2/25 3/4 3/5 3/12 3/17 3/24 3/29',
  '一粒万倍日 1〜3月', ichiryu.slice(0, 17).join(' '));

// 最強開運日: 2026-03-05 は 天赦日+一粒万倍日+寅の日+大安
const sup = KICHI.ofDayNum(dayNum(2026, 3, 5));
check(sup.names.join('+') === '天赦日+一粒万倍日+寅の日+大安' && sup.supreme === true,
  '2026-03-05 = 最強開運日', sup.names.join('+'));

// 二十四節気（2026年・国立天文台の暦要項と一致すること）
console.log('④ 二十四節気（節入り日）');
const SEKKI_2026 = { 1: '2/4', 2: '3/5', 3: '4/5', 4: '5/5', 5: '6/6', 6: '7/7',
                     7: '8/7', 8: '9/7', 9: '10/8', 10: '11/7', 11: '12/7' };
for (const [sm, want] of Object.entries(SEKKI_2026)) {
  let got = '';
  for (let m = 1; m <= 12 && !got; m++) {
    const dim = new Date(Date.UTC(2026, m, 0)).getUTCDate();
    for (let d = 1; d <= dim; d++) {
      const n = dayNum(2026, m, d);
      if (ALM.setsuMonth(n) === +sm && ALM.setsuMonth(n - 1) !== +sm) { got = `${m}/${d}`; break; }
    }
  }
  check(got === want, `節月${sm}月の入り → ${want}`, got !== want ? `実際: ${got}` : '');
}

console.log(failures === 0 ? '\n✅ 全テストパス' : `\n❌ ${failures}件の不一致`);
process.exit(failures === 0 ? 0 : 1);
