#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ゲームリスト更新スクリプトの回帰テスト（ネットワーク不要）
==========================================================
サ終タイトルが延々とプルダウンに残っていた原因は、生存確認が
「iTunes 検索が何かヒットしたか」しか見ておらず、あいまい検索が返す
無関係なアプリで常に生存判定になっていたこと。ここではその照合ロジックと、
セルラン付与・除外までの一連の流れをモックで検証する。

実行:  python3 test_games.py
終了コード 0 = 全件パス / 1 = 失敗あり
"""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('ug', os.path.join(HERE, 'update_games.py'))
ug = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ug)

failures = 0


def check(ok, label, detail=''):
    global failures
    if ok:
        print('  ✅ ' + label)
    else:
        failures += 1
        print('  ❌ ' + label + (('\n     ' + detail) if detail else ''))


# ── ① タイトル照合 ────────────────────────────────────────
print('① ストア名がそのタイトル自身かの照合')
CASES = [
    # (ストア上の名前, (value, label, term), 期待スコア)  2=完全一致 1=包含 0=別物
    ('原神', ('原神', '原神', '原神'), 2),
    ('原神 - Genshin Impact', ('原神', '原神', '原神'), 1),
    ('Pokémon Trading Card Game Pocket',
     ('Pokémon Trading Card Game Pocket', 'Pokémon TCG Pocket',
      'ポケポケ Pokémon Trading Card Game Pocket'), 2),
    ('#コンパス 戦闘摂理解析システム',
     ('コンパス', '＃コンパス 戦闘摂理解析システム', '#コンパス 戦闘摂理解析システム'), 2),
    ('ウマ娘 プリティーダービー', ('ウマ娘', 'ウマ娘 プリティーダービー', 'ウマ娘 プリティーダービー'), 2),
    ('プリンセスコネクト！Re:Dive',
     ('プリコネR', 'プリンセスコネクト！Re:Dive', 'プリンセスコネクト Re:Dive'), 2),
    ('崩壊3rd', ('崩壊3rd', '崩壊3rd', '崩壊3rd'), 2),
    # ↓ サ終タイトルを検索したときに返ってきがちな無関係アプリ（旧実装はここで生存判定していた）
    ('パズル＆ドラゴンズ', ('ドルウェブ', 'ドルウェブ', 'ドルウェブ'), 0),
    ('アイドルマスター シャイニーカラーズ', ('ドルウェブ', 'ドルウェブ', 'ドルウェブ'), 0),
    ('ファンタシースターオンライン2 ニュージェネシス',
     ('PSO2es', 'PSO2es', 'ファンタシースターオンライン2 es'), 0),
    ('モンスターストライク', ('ゆるドラ', 'ゆるドラシル', 'ゆるドラシル'), 0),
    # ↓ 同一シリーズの別タイトル（略称で包含一致を許すと取り違える）
    ('アサルトリリィ BOUQUET',
     ('アサルトリリィ', 'アサルトリリィ Last Bullet', 'アサルトリリィ Last Bullet'), 0),
    ('崩壊：スターレイル', ('崩壊3rd', '崩壊3rd', '崩壊3rd'), 0),
    ('七つの大罪 グランドクロス',
     ('七つの大罪：Origin', '七つの大罪：Origin', '七つの大罪 Origin'), 0),
]
for store, (v, l, t), want in CASES:
    got = ug.title_match_score(store, v, l, t)
    check(got == want, f'{store} × {l} → {got}', f'期待 {want}')

# 攻略ガイドより本編（ゲームカテゴリ）を優先して選ぶ
guide = {'trackName': '原神 攻略ガイド', 'primaryGenreId': 6018, 'trackId': 9}
real = {'trackName': '原神', 'primaryGenreId': 6014, 'trackId': 1}
best, best_key = None, (0, 0)
for r in (guide, real):
    k = (ug.title_match_score(r['trackName'], '原神', '原神', '原神'), 1 if ug.is_game_app(r) else 0)
    if k[0] > 0 and k > best_key:
        best, best_key = r, k
check(best is real, '攻略ガイドではなく本編を選ぶ', best and best['trackName'])

# ── ② サービス終了告知の検出 ────────────────────────────
print('② ストア説明文のサービス終了告知')
check(ug.eos_notice({'description': '2026年10月31日をもちましてサービス終了とさせていただきます。'})
      == 'サービス終了', '終了告知を検出する')
check(ug.eos_notice({'description': '期間限定イベント開催中！', 'releaseNotes': '不具合を修正しました'})
      is None, '通常の説明文では誤検出しない')

# ── ③ セルランの索引 ────────────────────────────────────
print('③ 売上ランキング（セルラン）の付与')
grossing = [{'name': 'モンスターストライク', 'id': '1', 'rank': 1},
            {'name': 'ウマ娘 プリティーダービー', 'id': '2', 'rank': 5},
            {'name': '原神', 'id': '3', 'rank': 12},
            {'name': 'Fate/Grand Order', 'id': '4', 'rank': 30}]
by_name, by_id = ug.build_rank_index(grossing)
for app_id, names, want in [
        (None, ['原神', '原神', None], 12),
        ('2', ['ウマ娘', 'ウマ娘 プリティーダービー', None], 5),
        (None, ['Fate/GO', 'Fate/Grand Order', None], 30),
        (None, ['白猫', '白猫プロジェクト', None], None)]:
    got = ug.lookup_rank(by_name, by_id, app_id, names)
    check(got == want, f'{names[1]} → {got}位' if got else f'{names[1]} → 圏外', f'期待 {want}')

# ── ④ セルランのスクレイピング（AppMedia / Game-i）──────
print('④ セルランの取得と合成')
_G = ['モンスターストライク', 'ドラゴンボールZ ドッカンバトル', 'プロ野球スピリッツA',
      'パズル＆ドラゴンズ', 'Fate/Grand Order', '原神', 'ウマ娘 プリティーダービー',
      'ブルーアーカイブ', '崩壊：スターレイル', '勝利の女神：NIKKE']
_NON = ['LINE', 'YouTube', 'ピッコマ', 'Tinder', 'PayPay', 'TVer']


def _table(n, names, with_kurai):
    h = '<html><body><table><tr><th>順位</th><th>アプリ</th><th>売上</th></tr>'
    for i in range(1, n + 1):
        g = names[(i - 1) % len(names)] + ('' if i <= len(names) else str(i))
        r = f'{i}位' if with_kurai else str(i)
        h += f'<tr><td>{r}</td><td><a href="/x">{g}</a></td><td>1,234,567円</td><td>↑2</td></tr>'
    return h + '</table></body></html>'


def _list(n, names):
    h = '<html><body><ol>'
    for i in range(1, n + 1):
        g = names[(i - 1) % len(names)] + ('' if i <= len(names) else str(i))
        h += f'<li><span>{i}</span><span>{g}</span><span>+3</span></li>'
    return h + '</ol></body></html>'


APPMEDIA_HTML = _table(100, _G, False)

check(len(ug.parse_rank_rows(APPMEDIA_HTML, 100)) == 100, '表組みから100件抽出')
check(len(ug.parse_rank_rows(_list(100, _G), 100)) == 100, 'リスト構造からも100件抽出')
check(ug.parse_rank_rows(APPMEDIA_HTML, 100)[0] == {'rank': 1, 'name': _G[0], 'id': None},
      '1位の順位と名前が取れる')
check(len(ug.parse_rank_rows('<html><body><p>メンテナンス中</p></body></html>', 100)) == 0,
      '中身の無いページからは0件')
check(ug.validate_ranks(ug.parse_rank_rows(APPMEDIA_HTML, 100), 3, 30, 't') is True,
      '正常なランキングは検証を通る')
check(ug.validate_ranks([], 3, 30, 't') is False, '空の結果は検証で弾く')
check(ug.is_non_game('LINE') and ug.is_non_game('ピッコマ') and ug.is_non_game('YouTube'),
      'ゲーム以外を判定できる')
check(not ug.is_non_game('原神') and not ug.is_non_game('ブルーアーカイブ'),
      'ゲームを誤って除外しない')

# Game-i は <article class="gi-ranking-item"> 構造（実ページから起こしたフィクスチャ）
def _gamei_article(rank, name, appid, cat):
    return (f'<article class="gi-ranking-item">'
            f'<div class="gi-rank rank-{rank}"><strong>{rank}</strong><span class="up">▲3</span></div>'
            f'<a href="https://game-i.daa.jp/?APP/{appid}">'
            f'<img class="gi-icon" src="https://example.invalid/x.jpg" alt="{name}のアイコン" width="48">'
            f'<div class="gi-name">{name}</div><div class="gi-company">Some Co</div>'
            f'<div class="gi-meta">{cat}</div></a>'
            f'<a class="gi-chip" href="#">5min</a></article>')


_GAMEI_ROWS = [(1, 'ChatGPT', '6448311069', 'Productivity'),
               (2, 'YouTube', '544007664', 'Photo & Video'),
               (3, 'モンスターストライク', '1', 'Games'),
               (4, 'ピッコマ', '2', 'Books'),
               (5, '原神', '3', 'Games')]
_GAMEI_ROWS += [(i, ('原神' if i % 3 else 'LINE') + str(i), str(i),
                 'Games' if i % 3 else 'Social Networking') for i in range(6, 301)]
GAMEI_HTML = ('<html><body><div class="gi-ranking-list">'
              + ''.join(_gamei_article(*r) for r in _GAMEI_ROWS) + '</div></body></html>')

_gi = ug.parse_gamei(GAMEI_HTML, 300)
check(len(_gi) == 300, 'Game-i の article 構造から300件抽出', f'実際 {len(_gi)}件')
check(_gi[0]['rank'] == 1 and _gi[0]['name'] == 'ChatGPT' and _gi[0]['id'] == '6448311069',
      '順位・アプリ名・アプリIDが取れる', str(_gi[0]))
check(_gi[0]['category'] == 'Productivity', 'ストアのカテゴリが取れる', str(_gi[0]))
check(not ug.is_game_entry(_gi[0]) and not ug.is_game_entry(_gi[1]) and not ug.is_game_entry(_gi[3]),
      'カテゴリでゲーム以外（ChatGPT/YouTube/ピッコマ）を除外')
check(ug.is_game_entry(_gi[2]) and ug.is_game_entry(_gi[4]),
      'カテゴリがGamesのものは残す')
check(ug.is_game_entry({'rank': 1, 'name': '原神', 'category': 'Games / Role Playing'}),
      'ゲームのサブカテゴリ表記でも残す')
check(not ug.is_game_entry({'rank': 1, 'name': 'GoodNovel(グッドノベル)', 'category': 'Books'}),
      'カテゴリがあるなら未知の名前でも非ゲームとして落とす')
check(not ug.is_game_entry({'rank': 1, 'name': 'netkeiba', 'category': 'Sports'}),
      'Sports など紛らわしいカテゴリも落とす')
check(ug.is_game_entry({'rank': 1, 'name': '原神', 'category': 'ゲーム'}), '日本語のカテゴリ表記も通る')
check(not ug.is_game_entry({'rank': 1, 'name': 'LINE', 'category': ''})
      and ug.is_game_entry({'rank': 1, 'name': '原神', 'category': ''}),
      'カテゴリが無い場合はキーワードで判定')

_orig_http = ug._http_text
_orig_itunes = ug.fetch_itunes_ranking
try:
    ug.fetch_itunes_ranking = lambda: ([{'name': 'モンスターストライク', 'id': '1', 'rank': 1}],
                                       [{'name': '新作RPG', 'id': '99', 'rank': 1}])

    def _http_ok(url, timeout=30):
        if 'appmedia' in url:
            return APPMEDIA_HTML
        if 'game-i' in url:
            return GAMEI_HTML
        raise Exception('unknown')
    ug._http_text = _http_ok
    g, f, src = ug.fetch_ranking()
    ranks = {e['rank']: e['name'] for e in g}
    check('AppMedia' in src and 'Game-i' in src, f'両方から取得する（{src}）')
    check(1 in ranks and 100 in ranks, '1〜100位が埋まる')
    check(max(ranks) > 100, '101位以降も埋まる')
    check(not [n for n in ranks.values() if ug.is_non_game(n)],
          'ゲーム以外が最終結果に残らない')

    def _http_ng(url, timeout=30):
        raise Exception('down')
    ug._http_text = _http_ng
    g2, f2, src2 = ug.fetch_ranking()
    check(src2.startswith('iTunes'), f'両方失敗すると iTunes RSS に落ちる（{src2}）')

    def _http_gamei_only(url, timeout=30):
        if 'game-i' in url:
            return GAMEI_HTML
        raise Exception('down')
    ug._http_text = _http_gamei_only
    g3, f3, src3 = ug.fetch_ranking()
    # 1位がゲーム以外なら除外されるので、先頭は必ずしも1位にならない（順位は詰めない）
    check('Game-i' in src3 and g3 and g3[0]['rank'] <= 10 and len(g3) > 100,
          'AppMedia だけ落ちたら Game-i が上位から埋める',
          f"先頭 {g3[0]['rank'] if g3 else '-'}位 / {len(g3)}件")
finally:
    ug._http_text = _orig_http
    ug.fetch_itunes_ranking = _orig_itunes


# ── ⑤ 除外までの一連の流れ ──────────────────────────────
print('⑤ サ終タイトルが GRACE_DAYS 日で消えるか')
ALIVE = {'原神': 1, 'ウマ娘 プリティーダービー': 2}
SEED = [('原神', '原神', '原神'),
        ('ウマ娘', 'ウマ娘 プリティーダービー', 'ウマ娘 プリティーダービー'),
        ('ドルウェブ', 'ドルウェブ', 'ドルウェブ')]
GROSSING = [{'name': 'ウマ娘 プリティーダービー', 'id': '2', 'rank': 3},
            {'name': '原神', 'id': '1', 'rank': 9}]


def fake_search(term):
    for name, tid in ALIVE.items():
        if ug.title_match_score(name, term, term, term) > 0:
            return [{'trackName': name, 'trackId': tid, 'primaryGenreId': 6014,
                     'description': '楽しいゲームです'}], True
    # サ終タイトルには無関係なアプリだけが返る
    return [{'trackName': 'パズル＆ドラゴンズ', 'trackId': 777, 'primaryGenreId': 6014,
             'description': 'パズルRPG'}], True


def fake_lookup(app_id):
    for name, tid in ALIVE.items():
        if str(tid) == str(app_id):
            return {'trackName': name, 'trackId': tid, 'primaryGenreId': 6014,
                    'description': '楽しいゲームです'}, True
    return None, True      # 配信停止


orig = (ug.SEED, ug.SEARCH_SLEEP, ug.fetch_ranking, ug.itunes_search, ug.itunes_lookup, ug.OUT)
cwd = os.getcwd()
try:
    ug.SEED, ug.SEARCH_SLEEP = SEED, 0
    ug.fetch_ranking = lambda: (GROSSING, [], 'テスト')
    ug.itunes_search, ug.itunes_lookup = fake_search, fake_lookup
    tmp = tempfile.mkdtemp()
    os.chdir(tmp)
    ug.OUT = 'games.json'
    seen = []
    for _ in range(ug.GRACE_DAYS + 1):
        ug.main()
        d = json.load(open('games.json', encoding='utf-8'))
        seen.append(len(d['playing']))
    check(seen[0] == 3 and seen[-1] == 2,
          f'猶予中は残り、{ug.GRACE_DAYS}日で消える（playing: {seen}）')
    check([e['label'] for e in d['eos']] == ['ドルウェブ'], 'eos にサ終タイトルが記録される',
          str(d['eos']))
    ranks = {g['value']: g.get('rank') for g in d['playing']}
    check(ranks == {'原神': 9, 'ウマ娘': 3}, 'プレイ中タイトルにセルランが付く', str(ranks))
finally:
    os.chdir(cwd)
    ug.SEED, ug.SEARCH_SLEEP, ug.fetch_ranking, ug.itunes_search, ug.itunes_lookup, ug.OUT = orig

print('\n✅ 全テストパス' if failures == 0 else f'\n❌ {failures}件の失敗')
sys.exit(0 if failures == 0 else 1)
