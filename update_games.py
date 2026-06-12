#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GACHA ORACLE ゲームタイトル自動更新スクリプト
================================================
毎日 GitHub Actions で実行し games.json を生成する。

仕組み:
 1. プレイ中タイトル(SEED): iTunes Search APIで毎日生存確認。
    App Storeから消えた(=サ終/配信停止)状態が GRACE_DAYS 日連続したら自動でリストから除外。
 2. 人気タイトル(TRENDING): App Store日本のゲームカテゴリ
    「セールスランキング上位200」+「無料ランキング上位100(新作検知用)」を毎日取得。
    新リリースはランクインした時点で自動追加、サ終したゲームはランキングから
    消える=自動的にリストから消える。
 3. 出力: games.json（index.htmlが起動時に読み込んでプルダウンを再構築）
"""
import json, time, unicodedata, urllib.request, urllib.parse, datetime, os, sys

GRACE_DAYS = 3          # 連続で見つからなかったら除外するまでの日数
SEARCH_SLEEP = 3.0      # iTunes Search APIのレート制限対策(約20回/分)
OUT = 'games.json'

# ── プレイ中タイトル（value=アプリ内で使うID/GAME_DBキーと一致させる, label=表示名, term=検索語 ──
SEED = [
    ("コンパス","＃コンパス 戦闘摂理解析システム","#コンパス 戦闘摂理解析システム"),
    ("AFKアリーナ","AFKアリーナ","AFKアリーナ"),
    ("Alterna","Alterna","Alterna ゲーム"),
    ("Black Desert Mobile","黒い砂漠モバイル","黒い砂漠モバイル"),
    ("Call of Duty","Call of Duty: Mobile","Call of Duty Mobile"),
    ("DQウォーク","ドラゴンクエストウォーク","ドラゴンクエストウォーク"),
    ("Echocalypse","Echocalypse -緋紅の神約-","エコカリプス"),
    ("Evertale","Evertale","Evertale"),
    ("Fate/GO","Fate/Grand Order","Fate/Grand Order"),
    ("LINE MF","LINE：モンスターファーム","LINE モンスターファーム"),
    ("Master Duel","遊戯王 マスターデュエル","遊戯王 マスターデュエル"),
    ("NIKKE","勝利の女神：NIKKE","勝利の女神 NIKKE"),
    ("Pokémon Trading Card Game Pocket","Pokémon TCG Pocket","ポケポケ Pokémon Trading Card Game Pocket"),
    ("Pokémon GO","Pokémon GO","Pokémon GO"),
    ("PokémonMaster","ポケモンマスターズ EX","ポケモンマスターズ EX"),
    ("PSO2es","PSO2es","ファンタシースターオンライン2 es"),
    ("PUBG","PUBG MOBILE","PUBG MOBILE"),
    ("アサルトリリィ","アサルトリリィ Last Bullet","アサルトリリィ Last Bullet"),
    ("アズールレーン","アズールレーン","アズールレーン"),
    ("アリスギア","アリス・ギア・アイギス","アリスギアアイギス"),
    ("うたわれLF","うたわれるもの ロストフラグ","うたわれるもの ロストフラグ"),
    ("ウマ娘","ウマ娘 プリティーダービー","ウマ娘 プリティーダービー"),
    ("おねがい社長！","おねがい社長！","おねがい社長"),
    ("カゲマス","陰の実力者になりたくて！マスターオブガーデン","陰の実力者になりたくて マスターオブガーデン"),
    ("グラクロ","七つの大罪 グランドクロス","七つの大罪 グランドクロス"),
    ("グラブル","グランブルーファンタジー","グランブルーファンタジー"),
    ("けもフレ3","けものフレンズ3","けものフレンズ3"),
    ("ゼンレスゾーンゼロ","ゼンレスゾーンゼロ","ゼンレスゾーンゼロ"),
    ("チェンクロ","チェインクロニクル","チェインクロニクル"),
    ("ツムツム","LINE：ディズニー ツムツム","ディズニー ツムツム"),
    ("ディスガイアRPG","魔界戦記ディスガイアRPG","魔界戦記ディスガイアRPG"),
    ("ドルウェブ","ドルウェブ","ドルウェブ"),
    ("ぷよクエ","ぷよぷよ!!クエスト","ぷよぷよクエスト"),
    ("プリコネR","プリンセスコネクト！Re:Dive","プリンセスコネクト Re:Dive"),
    ("ブルーアーカイブ","ブルーアーカイブ","ブルーアーカイブ"),
    ("ブレソル","BLEACH Brave Souls","BLEACH Brave Souls"),
    ("ヘブバン","ヘブンバーンズレッド","ヘブンバーンズレッド"),
    ("まおりゅう","転スラ 魔王と竜の建国譚","転生したらスライムだった件 魔王と竜の建国譚"),
    ("まどドラ","マギアエクセドラ","まどか マギカ Magia Exedra"),
    ("ゆるドラ","ゆるドラシル","ゆるドラシル"),
    ("ロススト","ロススト","ロススト"),
    ("陰陽師本格幻想","陰陽師 本格幻想RPG","陰陽師 本格幻想RPG"),
    ("俺だけレベルアップな件：Arise","俺だけレベルアップな件:ARISE","俺だけレベルアップな件 ARISE"),
    ("原神","原神","原神"),
    ("荒野行動","荒野行動","荒野行動"),
    ("走れ！女神","走れ！女神","走れ 女神"),
    ("白猫","白猫プロジェクト","白猫プロジェクト"),
    ("崩壊：スターレイル","崩壊：スターレイル","崩壊 スターレイル"),
    ("崩壊3rd","崩壊3rd","崩壊3rd"),
    ("無期迷途","無期迷途","無期迷途"),
    ("鳴潮","鳴潮","鳴潮"),
    ("STAR DIVE","STAR DIVE","スターダイブ STAR DIVE"),
    ("Gジェネ ET","SDガンダム ジージェネレーション エターナル","ジージェネレーション エターナル"),
    ("七つの大罪：Origin","七つの大罪：Origin","七つの大罪 Origin"),
    ("アークナイツ：エンドフィールド","アークナイツ：エンドフィールド","アークナイツ エンドフィールド"),
]

# ガチャ要素が無いことが明確なタイトルをランキングから除外
EXCLUDE_KEYWORDS = ['Minecraft','マインクラフト','スイカゲーム','Block Blast','Roblox',
                    '将棋','囲碁','麻雀 一人','ソリティア','ナンプレ','クロスワード','脳トレ']

UA = {'User-Agent': 'Mozilla/5.0 (GachaOracle GameListUpdater)'}

def norm(s):
    """名寄せ用正規化: 全半角統一・空白記号除去・小文字化"""
    s = unicodedata.normalize('NFKC', s).lower()
    return ''.join(c for c in s if c.isalnum())

def fetch_json(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def fetch_ranking():
    """App Store日本: ゲームカテゴリのランキングを取得（売上200+無料100）"""
    apps = []
    for url in [
        'https://itunes.apple.com/jp/rss/topgrossingapplications/limit=200/genre=6014/json',
        'https://itunes.apple.com/jp/rss/topfreeapplications/limit=100/genre=6014/json',
    ]:
        try:
            data = fetch_json(url)
            for e in data['feed']['entry']:
                name = e['im:name']['label']
                apps.append(name)
        except Exception as ex:
            print(f"[warn] ranking fetch failed: {url} -> {ex}", file=sys.stderr)
    return apps

def check_alive(term):
    """iTunes Search APIでApp Store(JP)に存在するか確認"""
    url = 'https://itunes.apple.com/search?' + urllib.parse.urlencode(
        {'term': term, 'country': 'JP', 'entity': 'software', 'limit': 5})
    try:
        d = fetch_json(url)
        return d.get('resultCount', 0) > 0
    except Exception as ex:
        print(f"[warn] search failed: {term} -> {ex}", file=sys.stderr)
        return None  # 通信失敗は判定保留（除外カウントを進めない）

def load_prev():
    if os.path.exists(OUT):
        try:
            return json.load(open(OUT, encoding='utf-8'))
        except Exception:
            pass
    return {}

def main():
    prev = load_prev()
    miss_state = prev.get('missState', {})   # {value: 連続未検出日数}

    # ── ① プレイ中タイトルの生存確認 ──
    playing, removed = [], []
    for value, label, term in SEED:
        alive = check_alive(term)
        time.sleep(SEARCH_SLEEP)
        if alive is True:
            miss_state[value] = 0
            playing.append({'value': value, 'label': label})
        elif alive is False:
            miss_state[value] = miss_state.get(value, 0) + 1
            if miss_state[value] >= GRACE_DAYS:
                removed.append(label)   # サ終扱い → リストから除外
                print(f"[info] 除外(連続{miss_state[value]}日未検出): {label}")
            else:
                playing.append({'value': value, 'label': label + ' ⚠'})
                print(f"[info] 未検出{miss_state[value]}日目(猶予中): {label}")
        else:  # 通信失敗 → 前回状態を維持して掲載継続
            playing.append({'value': value, 'label': label})

    # ── ② ランキング上位（新作の自動追加・サ終の自動消滅） ──
    seed_norms = {norm(v) for v, _, _ in SEED} | {norm(l) for _, l, _ in SEED}
    trending, seen = [], set()
    for name in fetch_ranking():
        n = norm(name)
        if not n or n in seen:
            continue
        if any(n.startswith(s) or s.startswith(n) for s in seed_norms if len(s) >= 2):
            continue  # プレイ中と重複
        if any(k.lower() in name.lower() for k in EXCLUDE_KEYWORDS):
            continue  # 非ガチャ
        seen.add(n)
        trending.append({'value': name, 'label': name})

    out = {
        'updated': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M JST'),
        'playing': playing,
        'trending': trending[:200],
        'removed': removed,
        'missState': miss_state,
    }
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"[done] playing={len(playing)} trending={len(out['trending'])} removed={len(removed)}")

if __name__ == '__main__':
    main()
