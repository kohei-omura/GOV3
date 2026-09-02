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

# ── ④ 除外までの一連の流れ ──────────────────────────────
print('④ サ終タイトルが GRACE_DAYS 日で消えるか')
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
    ug.fetch_ranking = lambda: (GROSSING, [])
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
