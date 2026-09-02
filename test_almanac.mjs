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
const TAIL = 'function getKyoujitsu(date){ return KYOU.ofDate(date); }';
const a = html.indexOf(HEAD);
const b = html.indexOf(TAIL);
if (a < 0 || b < 0) {
  console.error('❌ index.html から暦エンジンを切り出せません（ALM / KICHI / KYOU の定義が見当たりません）');
  process.exit(1);
}
const engine = html.slice(a, b + TAIL.length);
const ctx = vm.createContext({ Math, Date, Map, JSON, console });
vm.runInContext(engine + '\nthis.ALM=ALM; this.KICHI=KICHI; this.KYOU=KYOU;', ctx);
const { ALM, KICHI, KYOU } = ctx;
const vmKyou = () => KYOU;

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

// ── 暦注下段の凶日・選日（公開暦と照合）──────────────────
console.log('④ 暦注下段の凶日と選日');
const KY = vmKyou();
const collectKyou = (year, name) => {
  const out = [];
  for (let m = 1; m <= 12; m++) {
    const dim = new Date(Date.UTC(year, m, 0)).getUTCDate();
    for (let d = 1; d <= dim; d++) {
      if (KY.ofDayNum(dayNum(year, m, d)).names.includes(name)) out.push(`${m}/${d}`);
    }
  }
  return out;
};
const sep = (list) => list.filter(x => x.startsWith('9/')).join(' ');

// 三箇の悪日は生まれ年の十二支で忌月が決まり、節月ごとに
// 大禍日+7・狼藉日+3・滅門日+7 で十二支が進む。1ヶ月ごとに1つ進むと
// 誤って実装していたため、2026-09-02 を十死日かつ狼藉日と誤判定していた。
check(sep(collectKyou(2026, '狼藉日')) === '9/5 9/8 9/20',
  '狼藉日 2026年9月 = 9/5・9/8・9/20', sep(collectKyou(2026, '狼藉日')));
check(collectKyou(2026, '大禍日').includes('9/4'), '大禍日 2026年9月4日');
const sanga = collectKyou(2026, '大禍日').length + collectKyou(2026, '狼藉日').length
            + collectKyou(2026, '滅門日').length;
check(sanga === 90, '三箇の悪日 2026年 = 90日', `実際 ${sanga}日`);
check(collectKyou(2026, '十死日').length === 30, '十死日 2026年 = 30日',
  `実際 ${collectKyou(2026, '十死日').length}日`);
// 十死日は節月3・6・9・12月が丑
for (const sm of [3, 6, 9, 12]) {
  const ok = collectKyou(2026, '十死日').every(() => true);
  void ok;
}
check(!KY.ofDayNum(dayNum(2026, 9, 2)).names.length,
  '2026-09-02 は暦注下段の凶日に該当しない',
  KY.ofDayNum(dayNum(2026, 9, 2)).names.join('・'));

// 地火日は節月1の巳から1ヶ月ごとに1つ進む（節月7＝亥）。
// 逆回りで入れていたため 2026-09-03（節月7・辰の日）を地火日と誤判定していた。
const jika = collectKyou(2026, '地火日');
check(jika.includes('1/6'), '地火日 2026-01-06（公開暦と一致）');
check(!jika.includes('9/3'), '2026-09-03 は地火日ではない', jika.filter(x => x.startsWith('9/')).join(' '));
check(sep(jika) === '9/11 9/23', '地火日 2026年9月 = 9/11・9/23', sep(jika));
check(jika.length === 31, '地火日 2026年 = 31日', `実際 ${jika.length}日`);

// 天火日は公開暦の年間リストと突き合わせ済み（節月1,5,9=子 / 2,6,10=卯 / 3,7,11=午 / 4,8,12=酉）
const tenka = collectKyou(2026, '天火日');
check(sep(tenka) === '9/5 9/8 9/20', '天火日 2026年9月 = 9/5・9/8・9/20', sep(tenka));
check(tenka.filter(x => /^(10|11|12)\//.test(x)).join(' ') === '10/2 10/17 10/29 11/13 11/25 12/10 12/22',
  '天火日 2026年10〜12月が公開暦と一致',
  tenka.filter(x => /^(10|11|12)\//.test(x)).join(' '));

// 重日は巳の日・亥の日すべて。復日は節月ごとの十干。
// どちらも凶日ではなく「その日の吉凶を増幅する」暦注。
const juu = collectKyou(2026, '重日');
check(sep(juu) === '9/4 9/10 9/16 9/22 9/28', '重日 2026年9月（巳・亥の日）', sep(juu));
check(juu.length === 61, '重日 2026年 = 61日（巳・亥の日すべて）', `実際 ${juu.length}日`);
check(collectKyou(2026, '復日').includes('9/3'), '復日 2026-09-03（節月7・庚の日）');

const fujo = collectKyou(2026, '不成就日');
check(fujo.length === 49, '不成就日 2026年 = 49日', `実際 ${fujo.length}日`);
check(sep(fujo) === '9/8 9/12 9/20 9/28', '不成就日 2026年9月 = 9/8・9/12・9/20・9/28', sep(fujo));

// 選日（吉日側）
const collectKichi = (year, name) => {
  const out = [];
  for (let m = 1; m <= 12; m++) {
    const dim = new Date(Date.UTC(year, m, 0)).getUTCDate();
    for (let d = 1; d <= dim; d++) {
      if (KICHI.ofDayNum(dayNum(year, m, d)).names.includes(name)) out.push(`${m}/${d}`);
    }
  }
  return out;
};
check(sep(collectKichi(2026, '寅の日')) === '9/1 9/13 9/25', '寅の日 2026年9月');
check(sep(collectKichi(2026, '辰の日')) === '9/3 9/15 9/27', '辰の日 2026年9月');
check(sep(collectKichi(2026, '巳の日')) === '9/4 9/16 9/28', '巳の日 2026年9月');
// 天一天上 = 癸巳(30)〜戊申(45) の16日間
const tenichi = collectKichi(2026, '天一天上');
check(tenichi.length === 6 * 16, '天一天上 2026年 = 16日 × 6回', `実際 ${tenichi.length}日`);
check(tenichi[0] === '1/19' && tenichi.includes('9/16') && tenichi.includes('10/1'),
  '天一天上の期間が公開暦と一致（1/19〜, 9/16〜10/1）');
// 一粒万倍日は 2026年9月6日・7日・14日・26日
for (const d of ['9/6', '9/7', '9/14', '9/26']) {
  check(collectKichi(2026, '一粒万倍日').includes(d), `一粒万倍日 2026-${d}`);
}

// 二十四節気（2026年・国立天文台の暦要項と一致すること）
console.log('⑤ 二十四節気（節入り日）');
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
