#!/usr/bin/env node
/* ═══════════════════════════════════════════════════════════════
   画面まわりの回帰テスト（ブラウザ不要）
   ───────────────────────────────────────────────────────────────
   index.html の <script> を最小の DOM スタブ上で実行し、
   「実際にユーザーが踏んだ不具合」を再発させないことを確かめる。

     ① プレイ中タイトルの手動追加・削除が動くこと
     ② 追加ボタンが入力欄を潰さない指定になっていること
        （.rst-btn は width:100% なので横並びに置くと入力欄が消える）
     ③ 鑑定結果を sessionStorage から読み戻しても落ちないこと
        （Date が文字列に化けて date.getFullYear が落ちた）
     ④ 鑑定キャッシュのキーに生年月日などが入っていること

   実行:  node test_ui.mjs
   ═══════════════════════════════════════════════════════════════ */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const ROOT = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(ROOT, 'index.html'), 'utf8');

let failures = 0;
const check = (ok, label, detail) => {
  if (ok) console.log('  ✅ ' + label);
  else { failures++; console.log('  ❌ ' + label + (detail ? '\n     ' + detail : '')); }
};

// ── DOM スタブの上で index.html のスクリプトを動かす ──
function mkEl() {
  return { style: {}, classList: { add() {}, remove() {}, contains() { return false; } },
    dataset: {}, children: [], value: '', checked: false, innerHTML: '', textContent: '',
    appendChild(c) { this.children.push(c); return c; }, insertBefore(c) { this.children.push(c); return c; },
    removeChild() {}, contains() { return false; }, closest() { return null; },
    addEventListener() {}, removeEventListener() {}, remove() {},
    querySelector() { return null; }, querySelectorAll() { return []; },
    setAttribute() {}, getAttribute() { return null; }, scrollIntoView() {}, focus() {},
    getContext() { return null; }, insertAdjacentHTML() {} };
}
function boot(initialStore = {}) {
  const els = {};
  const store = Object.assign({}, initialStore);
  const ls = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); },
               removeItem: k => { delete store[k]; }, get length() { return Object.keys(store).length; } };
  const document = { getElementById(id) { return els[id] || (els[id] = mkEl()); },
    querySelector() { return null; }, querySelectorAll() { return []; }, createElement() { return mkEl(); },
    addEventListener() {}, body: mkEl(), documentElement: mkEl() };
  const ctx = { document, console, Math, Date, JSON, String, Number, Array, Object, parseInt, parseFloat,
    isNaN, setTimeout, setInterval: () => 0, clearInterval() {}, clearTimeout() {},
    requestAnimationFrame: () => 0, navigator: { userAgent: 'node' },
    location: { protocol: 'https:', hostname: 'localhost', href: 'https://localhost/', reload() {} },
    fetch: undefined, Intl, encodeURIComponent, decodeURIComponent, URL, Blob: function () {},
    btoa: s => Buffer.from(s, 'binary').toString('base64'), atob: s => Buffer.from(s, 'base64').toString('binary'),
    alert() {}, confirm() { return true; }, prompt() { return null; },
    Error, TypeError, RangeError, Promise, Symbol, Map, Set, WeakMap, RegExp, Boolean, Function };
  ctx.globalThis = ctx; ctx.self = ctx; ctx.window = ctx;
  ctx.addEventListener = () => {}; ctx.removeEventListener = () => {}; ctx.scrollTo = () => {};
  ctx.matchMedia = () => ({ matches: false, addEventListener() {} });
  ctx.innerWidth = 390; ctx.innerHeight = 844; ctx.localStorage = ls;
  vm.createContext(ctx);
  try { vm.runInContext(script, ctx, { filename: 'index.html' }); }
  catch (e) { console.error('❌ index.html のスクリプトが読み込めません: ' + e.message); process.exit(1); }
  ctx.__store = store; ctx.__els = els;
  return ctx;
}
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];
const ctx = boot();
const store = ctx.__store;
const document = ctx.document;

// ── ① プレイ中タイトルの手動追加・削除 ────────────────────────
console.log('① プレイ中タイトルの手動追加・削除');
ctx.GAMES_JSON = JSON.parse(readFileSync(join(ROOT, 'games.json'), 'utf8'));
ctx.SALES_RANK = {};
(ctx.GAMES_JSON.playing || []).forEach(g => { if (g.rank) ctx.SALES_RANK[g.value] = g.rank; });
const names = () => ctx.effectivePlaying().map(g => g.value);

const base = names();
check(base.length > 0, `自動更新の一覧 ${base.length}本を読み込む`);

document.getElementById('play-add-name').value = 'テスト新作RPG';
ctx.addPlayingTitle();
check(names().includes('テスト新作RPG'), '手動で追加できる');
check(ctx.effectivePlaying().find(g => g.value === 'テスト新作RPG').src === 'user',
  '追加分に「手動」の印が付く');

const victim = base[0];
ctx.removePlayingTitle(victim);
check(!names().includes(victim), `自動取得のタイトルを手動で削除できる（${victim}）`);

ctx.removePlayingTitle('テスト新作RPG');
check(!names().includes('テスト新作RPG'), '手動追加分も削除できる');

document.getElementById('play-add-name').value = victim;
ctx.addPlayingTitle();
check(names().includes(victim), '削除したタイトルを再追加すると復活する');

ctx.removePlayingTitle(victim);
ctx.resetPlayingOverrides();
check(JSON.stringify(names()) === JSON.stringify(base), '「自動更新の状態に戻す」で元に戻る');

const sus = ctx.effectivePlaying().filter(g => g.sunsetting);
check(sus.length > 0, `⚠要確認のタイトルが自動削除されず残っている（${sus.map(g => g.label).join('、')}）`);

// 要確認が先頭に来ること（55本の下の方に埋もれると気づけない）
ctx.renderPlayingList();
const listHtml = document.getElementById('play-list').innerHTML;
const firstRow = listHtml.split('</div><div ')[0];
check(firstRow.includes('要確認'), '一覧の先頭に ⚠要確認 のタイトルが来る');
check((listHtml.match(/✕ 削除/g) || []).length === ctx.effectivePlaying().length,
  '全行に「✕ 削除」ボタンが出る');

// ── ② 追加ボタンが入力欄を潰さないこと ────────────────────────
console.log('② 追加フォームの体裁');
const addRow = html.slice(html.indexOf('id="play-add-name"'), html.indexOf('id="play-filter"'));
check(/onclick="addPlayingTitle\(\)"/.test(addRow), '追加ボタンが存在する');
check(!/class="rst-btn"/.test(addRow),
  '追加ボタンに .rst-btn を使っていない（width:100% で入力欄が18pxに潰れる）');
check(/width:auto/.test(addRow), '追加ボタンの幅が auto（入力欄と共存できる）');
check(/id="play-manage"/.test(html) && /openPlayingManager\(\)/.test(html),
  'ゲーム選択の下から一覧編集へ飛べる導線がある');

// ── ③ 保存した鑑定結果を読み戻しても落ちない ──────────────────
console.log('③ 保存した鑑定結果の読み戻し');
check(typeof ctx.toDate === 'function', 'toDate() がある');
check(ctx.toDate('2026-09-02T00:00:00.000Z') instanceof Date, '文字列を Date に戻せる');
check(ctx.toDate(null) === null && ctx.toDate('') === null && ctx.toDate('でたらめ') === null,
  '不正な値は null になる');
let threw = null;
try { ctx.calLookup('2026-09-02T00:00:00.000Z'); ctx.calLookup(null); ctx.calLookup(undefined); }
catch (e) { threw = e.message; }
check(threw === null, 'calLookup に文字列や null を渡しても落ちない', threw);

// ── ③b 計算ロジックを直したら保存済みの結果が捨てられること ──
console.log('③b 古い鑑定結果の破棄');
check(typeof ctx.CALC_REV === 'string' && ctx.CALC_REV.length > 0, 'CALC_REV が定義されている');
check(store['gachaOracle_calcRev'] === ctx.CALC_REV,
  '読み込み時に計算リビジョンが記録される');
{
  // 前のリビジョンで保存された結果が残っている端末を再現し、開き直して消えるか見る
  const kept = '[{"value":"残すべき値","label":"残すべき値"}]';
  const s2 = boot({ gachaOracle_calcRev: 'old-rev', gachaOracle_result: '{"luckyTimes":[]}',
                    gachaOracle_key: 'v5|...', gachaOracle_breakdown: '{}', gachaOracle_history: '[]',
                    gachaOracle_playAdded: kept }).__store;
  check(s2['gachaOracle_result'] === undefined && s2['gachaOracle_breakdown'] === undefined,
    'リビジョンが変わると保存済みの鑑定結果が消える');
  check(s2['gachaOracle_calcRev'] === ctx.CALC_REV, '新しいリビジョンが書き込まれる');
  check(s2['gachaOracle_playAdded'] === kept, 'ユーザーが手で足したプレイ中タイトルは消さない');

  // 同じリビジョンなら消さない（毎回消えるとキャッシュの意味がない）
  const s3 = boot({ gachaOracle_calcRev: ctx.CALC_REV, gachaOracle_result: '{"luckyTimes":[]}' }).__store;
  check(s3['gachaOracle_result'] === '{"luckyTimes":[]}', 'リビジョンが同じなら保存済みの結果は残る');
}

// ── ④ 鑑定キャッシュのキー ────────────────────────────────────
console.log('④ 鑑定キャッシュのキー');
const keyLine = html.slice(html.indexOf('const cacheKey='), html.indexOf('const cacheKey=') + 400);
for (const f of ['CALC_REV', 'birthdate', 'zodiac', 'bloodType', 'eto', 'pickupRate', 'pityCount', 'currentPulls']) {
  check(keyLine.includes(f), `キャッシュキーに ${f} が入っている`);
}
check(/_calDate=toDate\(t\._calDate\)/.test(html.replace(/\s/g, '')),
  'キャッシュから戻すとき _calDate を Date に復元している');

console.log(failures === 0 ? '\n✅ 全テストパス' : `\n❌ ${failures}件の不一致`);
process.exit(failures === 0 ? 0 : 1);
