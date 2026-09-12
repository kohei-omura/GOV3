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

   実行:  node tests/test_ui.mjs
   ═══════════════════════════════════════════════════════════════ */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');   // リポジトリ直下
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
ctx.GAMES_JSON = JSON.parse(readFileSync(join(ROOT, 'data', 'games.json'), 'utf8'));
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

// ── ⑤ 候補日カードの重日・復日バッジ ────────────────────────
console.log('⑤ 候補日カードの重日・復日');
check(/ampNames:dKyou2\.names\.filter/.test(html.replace(/\s/g, '')),
  '候補日の情報に重日・復日を持たせている');
check(/\$\{\(t\.ampNames\|\|\[\]\)\.map/.test(html),
  '候補日カードで重日・復日のバッジを描いている');
{
  // 9/4 は辛巳 → 重日。凶日ではないので kyouNames ではなく ampNames 側に入る
  const n = Math.floor(Date.UTC(2026, 8, 4) / 86400000);
  const names = ctx.KYOU.ofDayNum(n).names;
  check(names.includes('重日') && names.includes('大禍日'),
    '2026-09-04 は大禍日かつ重日', names.join('・'));
  check(ctx.KYOU.META['重日'].penalty === 0 && ctx.KYOU.META['復日'].penalty === 0,
    '重日・復日は単独では減点しない（増幅のみ）');
}

// ── ⑥ 引きの記録（期待値との比較）と見送りログ ────────────────
console.log('⑥ 引きの記録と見送りログ');
{
  const BLUE = { rate: 0.7, pity: 200, soft: 0, step: 0, share: 1, nextGuar: false };
  const P = n => ctx.targetReachProb(BLUE, n);
  const near = (a, b) => Math.abs(a - b) < 0.005;

  check(near(P(10), 0.068) && near(P(30), 0.190) && near(P(100), 0.505),
    `連数ごとの到達確率が正しい（10連 ${(P(10) * 100).toFixed(1)}% / 30連 ${(P(30) * 100).toFixed(1)}%）`);
  check(P(200) > 0.9999, '天井まで回せば到達確率は100%');

  const rec = (pulls, res, hot) => ({ game: 'ブルーアーカイブ', pulls, res, hot, prm: BLUE, exp: P(pulls) });

  // 天井まで回した記録は、当たっても外れても評価に使わない。
  // ここを混ぜると「連数で押し切った」分が的中として積み上がってしまう。
  check(ctx.isInformative(rec(200, 'target')) === false, '天井まで回した記録は評価に使わない');
  check(ctx.isInformative(rec(30, 'target')) === true, '30連の記録は評価に使う');
  const pity = ctx.luckOf([rec(200, 'target'), rec(200, 'lose')]);
  check(pity.n === 0 && pity.flat === 2 && pity.diff === 0,
    '天井まで回した記録は加点も減点もしない', JSON.stringify(pity));

  // 少ない連数で当てたときだけ大きく効く
  const fast = ctx.luckOf([rec(30, 'target')]);
  const miss = ctx.luckOf([rec(30, 'lose')]);
  check(near(fast.diff, 0.81), `30連で目玉なら +0.81回分（実際 ${fast.diff.toFixed(2)}）`);
  check(near(miss.diff, -0.19), `30連で外れなら −0.19回分（実際 ${miss.diff.toFixed(2)}）`);

  // SSRのみ・爆死はどちらも「目玉に届かなかった」
  check(ctx.isTargetHit(rec(30, 'ssr')) === false && ctx.isTargetHit(rec(30, 'target')) === true,
    '目玉GETだけを当たりとして数える');

  // 仕様が分からないゲームは比較から外す
  check(ctx.expectTarget({ game: '架空のゲーム', pulls: 30 }) == null,
    'ガチャ仕様が分からない記録は期待値を出さない');

  // p値：差が無ければ有意にならない
  check(ctx.
    _twoSidedP(0) > 0.99 && ctx._twoSidedP(1.96) < 0.06 && ctx._twoSidedP(1.96) > 0.04,
    '両側p値が正しく出る');

  // 見送りログ
  check(typeof ctx.saveSkip === 'function' && typeof ctx.skips === 'function', '見送りログの関数がある');
  check(ctx.pityCostOf('ブルーアーカイブ') > 0 && ctx.pityCostOf('架空のゲーム') === 0,
    '天井までの概算額が出る（プリセットがある場合のみ）');

  // 断定しない表示になっていること
  check(!/オラクル的中率/.test(html), '「オラクル的中率」の看板を出していない');
  check(/偶然の範囲内です/.test(html), '有意でないときは偶然の範囲と明示する');
  check(/ガチャの結果はゲーム側の乱数で決まります/.test(html), '結果が乱数で決まることを明記している');
}

console.log(failures === 0 ? '\n✅ 全テストパス' : `\n❌ ${failures}件の不一致`);
process.exit(failures === 0 ? 0 : 1);
