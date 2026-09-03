#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GACHA ORACLE ゲームタイトル自動更新スクリプト v2
================================================
毎日 GitHub Actions で実行し games.json を生成する。

仕組み:
 1. プレイ中タイトル(SEED): App Store(JP)に「そのタイトル自身が」存在するかを毎日確認。
    見つからない状態が続いたら「終了の可能性」の印を付ける。
    ※ 自動削除はしない。ストア名の変更や検索のあいまいさで稼働中のタイトルを
      誤って消してしまう事故が起きたため、消すかどうかは利用者が画面から決める。
 2. セールスランキング: App Store日本のゲームカテゴリ売上200位を取得し、
    プレイ中タイトルにも順位(セルラン)を付ける。
 3. 人気タイトル(TRENDING): 売上200 +無料100(新作検知)。新作は自動追加、
    サ終はランキングから消える=自動的にリストから消える。
 4. 出力: games.json（index.htmlが起動時に読み込んでプルダウンを再構築）

v2 の変更点（サ終タイトルが消えないバグの修正）
-----------------------------------------------
v1 の生存確認は iTunes Search API に検索語を投げて resultCount > 0 を見るだけだった。
iTunes の検索はあいまい一致のため、サ終済みタイトルでも無関係なアプリが引っ掛かり、
常に「生存」と判定されていた（実際 missState は全タイトル 0 のまま、removed は空で、
サ終済みタイトルが延々とプルダウンに残り続けていた）。

  ① 検索結果の trackName が「そのタイトル自身か」を名寄せ照合するようにした。
  ② 一度でも同定できたら trackId を games.json に保存し、以後は /lookup?id= の
     完全一致判定に切り替える（あいまい検索を経由しないので誤判定しない）。
  ③ ストア説明文・更新履歴の「サービス終了」告知も未検出と同じ扱いにする。
  ④ 判定の根拠を games.json の checks に残し、なぜ消えた/残ったかを追えるようにした。

環境変数
--------
GAMES_DRY_RUN=1   games.json を書き出さずに判定結果だけ表示する
"""
import json, re, time, unicodedata, urllib.request, urllib.parse, datetime, os, sys

GRACE_DAYS = 3          # 連続で見つからなかったら除外するまでの日数
SEARCH_SLEEP = 3.0      # iTunes Search APIのレート制限対策(約20回/分)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'games.json')

# ── プレイ中タイトル（value=アプリ内で使うID/GAME_DBキーと一致させる, label=表示名, term=検索語 ──
SEED = [
    ("コンパス","＃コンパス 戦闘摂理解析システム","#コンパス 戦闘摂理解析システム"),
    ("AFKアリーナ","AFKアリーナ","AFKアリーナ"),
    ("Alterna","Alterna","Alterna ゲーム"),
    ("Black Desert Mobile","New 黒い砂漠 MOBILE","New 黒い砂漠 MOBILE"),
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
    ("PokémonMaster","ポケモンマスターズ EX","Pokémon Masters EX"),
    ("PSO2es","PSO2es","ファンタシースターオンライン2 es"),
    ("PUBG","PUBG MOBILE","PUBG MOBILE"),
    ("アサルトリリィ","アサルトリリィ Last Bullet","アサルトリリィ Last Bullet"),
    ("アズールレーン","アズールレーン","アズールレーン"),
    ("アリスギア","アリス・ギア・アイギス","アリスギアアイギス"),
    ("うたわれLF","うたわれるもの ロストフラグ","うたわれるもの ロストフラグ"),
    ("ウマ娘","ウマ娘 プリティーダービー","ウマ娘 プリティーダービー"),
    ("おねがい社長！","おねがい社長！","おねがい社長"),
    ("カゲマス","陰の実力者になりたくて！マスターオブガーデン","陰の実力者になりたくて マスターオブガーデン"),
    ("グラクロ","七つの大罪 光と闇の交戦 : グラクロ","七つの大罪 光と闇の交戦 グラクロ"),
    ("グラブル","グランブルーファンタジー","グランブルーファンタジー"),
    ("けもフレ3","けものフレンズ3","けものフレンズ3"),
    ("ゼンレスゾーンゼロ","ゼンレスゾーンゼロ","ゼンレスゾーンゼロ"),
    ("チェンクロ","チェインクロニクル","チェインクロニクル"),
    ("ツムツム","LINE：ディズニー ツムツム","ディズニー ツムツム"),
    ("ディスガイアRPG","魔界戦記ディスガイアRPG","魔界戦記ディスガイアRPG"),
    ("ドルウェブ","ドルフィンウェーブ","ドルフィンウェーブ"),
    ("ぷよクエ","ぷよぷよ!!クエスト","ぷよぷよクエスト"),
    ("プリコネR","プリンセスコネクト！Re:Dive","プリンセスコネクト Re:Dive"),
    ("ブルーアーカイブ","ブルーアーカイブ","ブルーアーカイブ"),
    ("ブレソル","BLEACH Brave Souls","BLEACH Brave Souls"),
    ("ヘブバン","ヘブンバーンズレッド","ヘブンバーンズレッド"),
    ("まおりゅう","転スラ 魔王と竜の建国譚","転生したらスライムだった件 魔王と竜の建国譚"),
    ("まどドラ","マギアエクセドラ","まどか マギカ Magia Exedra"),
    ("ゆるドラ","ゆるドラシル","ゆるドラシル"),
    ("ロススト","コードギアス 反逆のルルーシュ　ロストストーリーズ","コードギアス 反逆のルルーシュ ロストストーリーズ"),
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
    ("STAR DIVE","モンギル：STAR DIVE","モンギル STAR DIVE"),
    ("Gジェネ ET","SDガンダム ジージェネレーション エターナル","ジージェネレーション エターナル"),
    ("七つの大罪：Origin","七つの大罪：Origin","七つの大罪 Origin"),
    ("アークナイツ：エンドフィールド","アークナイツ：エンドフィールド","アークナイツ エンドフィールド"),
]

# ガチャ要素が無いことが明確なタイトルをランキングから除外
EXCLUDE_KEYWORDS = ['Minecraft','マインクラフト','スイカゲーム','Block Blast','Roblox',
                    '将棋','囲碁','麻雀 一人','ソリティア','ナンプレ','クロスワード','脳トレ']

UA = {'User-Agent': 'Mozilla/5.0 (GachaOracle GameListUpdater)'}

# ストア説明文にこれが出ていたら「サービス終了告知済み」とみなす
# （配信停止より先に告知が出るため、ストアから消える前に検知できる）
EOS_PATTERNS = ['サービス終了', 'サービスを終了', 'サービス提供を終了',
                '配信を終了', '配信終了のお知らせ', 'サービス終了日',
                'end of service', 'service will end']


def norm(s):
    """名寄せ用正規化: 全半角統一・空白記号除去・小文字化"""
    s = unicodedata.normalize('NFKC', s).lower()
    return ''.join(c for c in s if c.isalnum())


def fetch_json(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# ────────────────────────────────────────────
#  ランキング（セルラン）
#  1〜100位  : AppMedia のセルランページ
#  101位以降 : Game-i の App Store 売上ランキング
#  どちらも取得・検証に失敗したら iTunes RSS へフォールバックする。
#  Game-i はゲーム以外のアプリも載るため、ゲーム判定を通してから採用する。
# ────────────────────────────────────────────
APPMEDIA_URL = 'https://appmedia.jp/app_review/2607505'
GAMEI_URL    = 'https://game-i.daa.jp/?appstore-topgrossing'
APPMEDIA_MAX = 100      # AppMedia から採用する順位の上限
RANK_MAX     = 300      # 最終的に保持する順位の上限

# Game-i に載るゲーム以外のアプリ（日本の売上上位に常駐するもの）
NON_GAME_KEYWORDS = [
    'LINE', 'YouTube', 'Amazon', 'TVer', 'Netflix', 'Spotify', 'U-NEXT', 'ABEMA',
    'Disney', 'dアニメ', 'radiko', 'PayPay', 'メルカリ', 'Tinder', 'Pairs', 'ペアーズ',
    'with', 'タップル', 'Omiai', 'ピッコマ', 'LINEマンガ', 'コミックシーモア', 'めちゃコミ',
    'マガポケ', 'ジャンプ', 'マンガUP', 'マンガワン', 'Kindle', 'dマガジン', 'クックパッド',
    'Duolingo', 'Tinder', 'CapCut', 'Canva', 'Notion', 'Evernote', 'ChatGPT',
    'DAZN', 'Hulu', 'FOD', 'Lemino', 'Rakuten', '楽天', 'Yahoo', 'ヤフー',
    'ニコニコ', 'Pococha', 'IRIAM', 'SHOWROOM', '17LIVE', 'ふわっち', 'Bigo',
    'メロディ', 'ボイコネ', 'スマートニュース', 'NewsPicks', '日経', 'Tantan',
    'Zoom', 'Slack', 'Dropbox', 'Google', 'Apple', 'iCloud', 'マッチングアプリ',
]


def _http_text(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ('utf-8', 'euc-jp', 'cp932'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def strip_tags(html):
    html = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', html)
    html = re.sub(r'(?s)<[^>]+>', '\n', html)
    html = html.replace('&nbsp;', ' ').replace('&amp;', '&') \
               .replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
    return html


def is_non_game(name):
    n = name.lower()
    return any(k.lower() in n for k in NON_GAME_KEYWORDS) \
        or any(k.lower() in n for k in EXCLUDE_KEYWORDS)


def parse_rank_rows(html, limit):
    """順位とアプリ名の対を、表・リストのどちらの組み方でも拾えるように抽出する。

    行の単位（<tr> か <li>）ごとにタグを剥がし、最初に現れる 1〜999 の整数を順位、
    その後ろで最初に現れる「2文字以上の非数値テキスト」をアプリ名とみなす。
    サイト側の class 名やカラム構成に依存しないので、多少の改装では壊れない。
    """
    rows = re.findall(r'(?is)<tr[^>]*>(.*?)</tr>', html)
    if len(rows) < 20:
        rows = re.findall(r'(?is)<li[^>]*>(.*?)</li>', html)
    out, seen_rank = [], set()
    for row in rows:
        cells = [c.strip() for c in strip_tags(row).split('\n') if c.strip()]
        if len(cells) < 2:
            continue
        rank = None
        for i, c in enumerate(cells):
            m = re.fullmatch(r'(\d{1,3})位?', c)
            if m:
                rank = int(m.group(1))
                rest = cells[i + 1:]
                break
        if rank is None or not (1 <= rank <= 999) or rank in seen_rank:
            continue
        name = ''
        for c in rest:
            if len(c) >= 2 and not re.fullmatch(r'[\d\s.,%↑↓±+\-−–—位件人円]*', c):
                name = c
                break
        if not name:
            continue
        seen_rank.add(rank)
        out.append({'rank': rank, 'name': name, 'id': None})
    out.sort(key=lambda e: e['rank'])
    return [e for e in out if e['rank'] <= limit]


def validate_ranks(entries, need_top, min_count, source):
    """取得結果が「ランキングとして成立しているか」を確かめる。
    誤ったページを掴んだまま採用してしまうと、セルランが丸ごと嘘になるため。"""
    if len(entries) < min_count:
        print(f"[warn] {source}: 件数不足 {len(entries)}件 < {min_count}件", file=sys.stderr)
        return False
    ranks = [e['rank'] for e in entries]
    if min(ranks) > need_top:
        print(f"[warn] {source}: 先頭が{min(ranks)}位（{need_top}位以内が必要）", file=sys.stderr)
        return False
    if len(set(ranks)) != len(ranks):
        print(f"[warn] {source}: 順位が重複", file=sys.stderr)
        return False
    return True


def fetch_appmedia():
    """AppMedia のセルランページから 1〜100位を取得"""
    try:
        html = _http_text(APPMEDIA_URL)
    except Exception as ex:
        print(f"[warn] AppMedia 取得失敗: {ex}", file=sys.stderr)
        return []
    entries = parse_rank_rows(html, APPMEDIA_MAX)
    if not validate_ranks(entries, need_top=3, min_count=30, source='AppMedia'):
        return []
    print(f"[rank] AppMedia: {len(entries)}件（{entries[0]['rank']}〜{entries[-1]['rank']}位）")
    return entries


# App Store のカテゴリ名（gi-meta）でゲームか判定する。
# Game-i は各項目にストアの主カテゴリを併記しているので、キーワードよりも確実。
NON_GAME_CATEGORIES = {
    'productivity', 'photo & video', 'entertainment', 'social networking', 'music',
    'books', 'news', 'finance', 'shopping', 'lifestyle', 'utilities', 'education',
    'health & fitness', 'travel', 'food & drink', 'business', 'medical', 'navigation',
    'reference', 'weather', 'developer tools', 'graphics & design', 'stickers',
    'magazines & newspapers', 'newsstand',
    '仕事効率化', '写真/ビデオ', 'エンターテインメント', 'ソーシャルネットワーキング',
    'ミュージック', 'ブック', 'ニュース', 'ファイナンス', 'ショッピング', 'ライフスタイル',
    'ユーティリティ', '教育', 'ヘルスケア/フィットネス', '旅行', 'フード/ドリンク',
    'ビジネス', 'メディカル', 'ナビゲーション', '辞書/辞典/その他', '天気',
}


def parse_gamei(html, limit):
    """Game-i の売上ランキングを抽出する。

    ページ構造（2026-09 時点）:
        <article class="gi-ranking-item">
          <div class="gi-rank rank-1"><strong>1</strong><span class="up">▲3</span></div>
          <a href=".../?APP/6448311069"><img class="gi-icon" alt="ChatGPTのアイコン" ...>
            ...<div class="gi-company">…</div><div class="gi-meta">Productivity</div></a>
        </article>
    順位・アプリ名・ストアのカテゴリが1ブロックに揃っているので、
    ゲーム以外の判定はキーワードではなくカテゴリで行える。
    戻り値の各要素に category を持たせ、呼び出し側で除外する。
    """
    out = []
    for m in re.finditer(r'(?is)<article[^>]*class="[^"]*gi-ranking-item[^"]*"[^>]*>(.*?)</article>', html):
        block = m.group(1)
        rm = re.search(r'(?is)class="[^"]*gi-rank[^"]*"[^>]*>\s*<strong>\s*(\d{1,4})\s*</strong>', block)
        if not rm:
            rm = re.search(r'(?is)class="[^"]*gi-rank[^"]*rank-(\d{1,4})', block)
        if not rm:
            continue
        rank = int(rm.group(1))
        if not (1 <= rank <= 999) or rank > limit:
            continue
        # アプリ名: アイコンの alt（"◯◯のアイコン"）が最も安定
        name = ''
        am = re.search(r'(?is)<img[^>]*class="[^"]*gi-icon[^"]*"[^>]*\balt="([^"]+)"', block)
        if not am:
            am = re.search(r'(?is)\balt="([^"]+)のアイコン"', block)
        if am:
            name = re.sub(r'のアイコン$', '', am.group(1)).strip()
        if not name:
            nm = re.search(r'(?is)<div[^>]*class="[^"]*gi-(?:name|title|app)[^"]*"[^>]*>(.*?)</div>', block)
            if nm:
                name = strip_tags(nm.group(1)).strip().split('\n')[0].strip()
        if not name:
            continue
        cm = re.search(r'(?is)<div[^>]*class="[^"]*gi-meta[^"]*"[^>]*>(.*?)</div>', block)
        category = strip_tags(cm.group(1)).strip().split('\n')[0].strip() if cm else ''
        appid = None
        im = re.search(r'\?APP/(\d+)', block)
        if im:
            appid = im.group(1)
        out.append({'rank': rank, 'name': name, 'id': appid, 'category': category})
    out.sort(key=lambda e: e['rank'])
    # 同順位が複数出た場合は先勝ち
    seen, uniq = set(), []
    for e in out:
        if e['rank'] in seen:
            continue
        seen.add(e['rank'])
        uniq.append(e)
    return uniq


def is_game_entry(entry, trust_category=True):
    """Game-i の1件がゲームかどうか。

    Game-i は App Store の主カテゴリ（gi-meta）を併記しており、ゲームは "Games"、
    それ以外は "Productivity" / "Books" などが入る。カテゴリがあるならそれを信じる
    のが最も確実なので、既知の非ゲームに限らず「ゲームと書かれていないもの」は
    すべて除外する。カテゴリが取れないときだけキーワード判定に落とす。

    trust_category=False は保険。カテゴリの表記が想定と違って大半が落ちてしまった
    場合に、呼び出し側がキーワード判定でやり直すために使う。
    """
    cat = (entry.get('category') or '').strip().lower()
    if cat and trust_category:
        return 'game' in cat or 'ゲーム' in cat
    if cat:
        if 'game' in cat or 'ゲーム' in cat:
            return True
        if cat in NON_GAME_CATEGORIES:
            return False
    return not is_non_game(entry['name'])


def fetch_gamei(min_rank):
    """Game-i の App Store 売上ランキングから min_rank 位以降を取得。
    ゲーム以外のアプリが混ざるため、ストアのカテゴリで除外してから採用する。
    順位は詰めずに実際の App Store 順位のまま保つ。"""
    try:
        html = _http_text(GAMEI_URL)
    except Exception as ex:
        print(f"[warn] Game-i 取得失敗: {ex}", file=sys.stderr)
        return []
    entries = parse_gamei(html, RANK_MAX)
    if not entries:                      # 構造が変わった場合は汎用パーサで拾い直す
        entries = parse_rank_rows(html, RANK_MAX)
        print('[warn] Game-i: gi-ranking-item を検出できず汎用パーサにフォールバック', file=sys.stderr)
    if not validate_ranks(entries, need_top=10, min_count=80, source='Game-i'):
        return []
    target = [e for e in entries if e['rank'] >= min_rank]

    def split(trust):
        keep, drop = [], []
        for e in target:
            (keep if is_game_entry(e, trust) else drop).append(e)
        return keep, drop

    kept, dropped_e = split(True)
    # カテゴリの表記が想定と違って大半が落ちた場合はキーワード判定でやり直す
    if target and len(kept) < len(target) * 0.3:
        print(f"[warn] Game-i: カテゴリ判定で{len(kept)}/{len(target)}件しか残らないため "
              f"キーワード判定に切り替え", file=sys.stderr)
        kept, dropped_e = split(False)
    dropped = [f"{e['rank']}位 {e['name']}({e.get('category') or 'カテゴリ不明'})" for e in dropped_e]
    cats = {}
    for e in entries:
        cats[e.get('category') or '(なし)'] = cats.get(e.get('category') or '(なし)', 0) + 1
    top_cats = sorted(cats.items(), key=lambda kv: -kv[1])[:10]
    print(f"[rank] Game-i: カテゴリ内訳 {top_cats}")
    if dropped:
        print(f"[rank] Game-i: ゲーム以外を{len(dropped)}件除外 "
              f"({', '.join(dropped[:8])}{' ...' if len(dropped) > 8 else ''})")
    print(f"[rank] Game-i: {len(kept)}件（{min_rank}位以降）")
    return kept


def fetch_itunes_ranking():
    """フォールバック: iTunes RSS（ゲームカテゴリの売上200＋無料100）"""
    def rss(url):
        out = []
        try:
            data = fetch_json(url)
            for i, e in enumerate(data['feed']['entry'], 1):
                out.append({
                    'name': e['im:name']['label'],
                    'id': (e.get('id', {}).get('attributes', {}) or {}).get('im:id'),
                    'rank': i,
                })
        except Exception as ex:
            print(f"[warn] ranking fetch failed: {url} -> {ex}", file=sys.stderr)
        return out
    grossing = rss('https://itunes.apple.com/jp/rss/topgrossingapplications/limit=200/genre=6014/json')
    free = rss('https://itunes.apple.com/jp/rss/topfreeapplications/limit=100/genre=6014/json')
    return grossing, free


def fetch_ranking():
    """セルランを組み立てる。
    戻り値: (grossing, free, sources)
      grossing … {'name','id','rank'} の配列（1位から順）
      free     … 新作検知用（iTunes 無料ランキング）
      sources  … 表示用の取得元ラベル"""
    itunes_grossing, free = fetch_itunes_ranking()

    appmedia = fetch_appmedia()
    gamei = fetch_gamei(min_rank=(APPMEDIA_MAX + 1) if appmedia else 1)

    merged, used = {}, []
    for e in appmedia:
        merged[e['rank']] = e
    if appmedia:
        used.append(f'1〜{APPMEDIA_MAX}位 AppMedia')
    for e in gamei:
        merged.setdefault(e['rank'], e)
    if gamei:
        used.append(f"{gamei[0]['rank']}位以降 Game-i")

    if not merged:
        print('[rank] AppMedia / Game-i とも取得できず → iTunes RSS を使用', file=sys.stderr)
        return itunes_grossing, free, 'iTunes RSS（ゲーム）'

    # iTunes RSS にしか無いタイトルは順位を補完せず、ゲーム判定の材料としてのみ使う
    grossing = [merged[k] for k in sorted(merged)]
    return grossing, free, ' / '.join(used)


def build_rank_index(grossing):
    """セルラン検索用の索引。正規化名 → 順位 / trackId → 順位"""
    by_name, by_id = {}, {}
    for e in grossing:
        n = norm(e['name'])
        if n and n not in by_name:
            by_name[n] = e['rank']
        if e.get('id') and str(e['id']) not in by_id:
            by_id[str(e['id'])] = e['rank']
    return by_name, by_id


def lookup_rank(by_name, by_id, app_id, names):
    """そのタイトルの売上ランキング順位。圏外なら None"""
    if app_id and str(app_id) in by_id:
        return by_id[str(app_id)]
    cands = [norm(x) for x in names if x]
    for c in cands:
        if len(c) >= 2 and c in by_name:
            return by_name[c]
    # 表記ゆれ（"原神" と "原神 - Genshin Impact" 等）を包含関係で救う
    for rn, rank in by_name.items():
        for c in cands:
            if len(c) >= 4 and (c in rn or rn in c):
                return rank
    return None


# ────────────────────────────────────────────
#  生存確認
# ────────────────────────────────────────────
def title_match_score(store_name, value, label, term):
    """ストア上の名前が「そのタイトル自身」かを 2/1/0 で返す。
      2 = 完全一致（正規化後）
      1 = 包含一致（"原神" ⊂ "原神 - Genshin Impact" のようなサブタイトル付き表記）
      0 = 別物

    v1 は検索がヒットしたかどうかしか見ておらず、iTunes のあいまい検索が
    無関係なアプリを返すためサ終済みタイトルも生存判定になっていた。

    包含一致に使うのは label と term（正式名称）だけで、value は使わない。
    value はアプリ内部で使う略称なので、包含を許すと同じシリーズの別ゲーム
    （"アサルトリリィ Last Bullet" に対する "アサルトリリィ BOUQUET" 等）を
    取り違えてサ終を見逃す。この区別は外さないこと。
    """
    sn = norm(store_name)
    if not sn:
        return 0
    if any(norm(x or '') == sn for x in (value, label, term)):
        return 2
    for x in (label, term):
        c = norm(x or '')
        if len(c) >= 2 and len(sn) >= 2 and (c in sn or sn in c):
            return 1
    return 0


def is_game_app(res):
    """App Store の「ゲーム」カテゴリか。攻略本・非公式ガイドの誤検出を避ける"""
    if res.get('primaryGenreId') == 6014:
        return True
    return res.get('primaryGenreName') in ('ゲーム', 'Games')


def eos_notice(res):
    """ストア説明文・更新履歴にサービス終了の告知が出ているか"""
    blob = ((res.get('description') or '') + ' ' + (res.get('releaseNotes') or '')).lower()
    for pat in EOS_PATTERNS:
        if pat.lower() in blob:
            return pat
    return None


def itunes_lookup(app_id):
    """trackId による完全一致照会。配信停止済みなら resultCount=0 が返る。
    戻り値: (result or None, ok)  ok=False は通信失敗（判定保留）"""
    url = 'https://itunes.apple.com/lookup?' + urllib.parse.urlencode(
        {'id': app_id, 'country': 'JP'})
    try:
        d = fetch_json(url)
        rs = [r for r in d.get('results', []) if r.get('wrapperType') == 'software'
              or r.get('kind') == 'software']
        return (rs[0] if rs else None), True
    except Exception as ex:
        print(f"[warn] lookup failed: {app_id} -> {ex}", file=sys.stderr)
        return None, False


def itunes_search(term):
    """検索。戻り値: (results, ok)  ok=False は通信失敗（判定保留）"""
    url = 'https://itunes.apple.com/search?' + urllib.parse.urlencode(
        {'term': term, 'country': 'JP', 'entity': 'software', 'limit': 10})
    try:
        d = fetch_json(url)
        return d.get('results', []), True
    except Exception as ex:
        print(f"[warn] search failed: {term} -> {ex}", file=sys.stderr)
        return [], False


def check_title(value, label, term, app_id):
    """タイトル1件の生存判定。
    戻り値: {'alive': True/False/None, 'appId':.., 'name':.., 'reason':..}
      alive=None は通信失敗（未検出カウントを進めない）"""
    names = [value, label, term]

    # ① trackId を知っていれば完全一致で照会する（あいまい検索を経由しない）
    if app_id:
        res, ok = itunes_lookup(app_id)
        if not ok:
            return {'alive': None, 'appId': app_id, 'name': None, 'reason': '通信失敗'}
        if res is None:
            return {'alive': False, 'appId': app_id, 'name': None, 'reason': 'ストアから配信停止'}
        pat = eos_notice(res)
        if pat:
            return {'alive': False, 'appId': app_id, 'name': res.get('trackName'),
                    'reason': f'ストアに終了告知（{pat}）'}
        return {'alive': True, 'appId': app_id, 'name': res.get('trackName'), 'reason': ''}

    # ② 未知のタイトルは検索し、名前が一致した結果だけを採用する。
    #    完全一致 > 包含一致、同点ならゲームカテゴリを優先して最良の1件を選ぶ。
    results, ok = itunes_search(term)
    if not ok:
        return {'alive': None, 'appId': None, 'name': None, 'reason': '通信失敗'}
    best, best_key = None, (0, 0)
    for res in results:
        key = (title_match_score(res.get('trackName', ''), value, label, term),
               1 if is_game_app(res) else 0)
        if key[0] > 0 and key > best_key:
            best, best_key = res, key
    if best is not None:
        pat = eos_notice(best)
        if pat:
            return {'alive': False, 'appId': best.get('trackId'), 'name': best.get('trackName'),
                    'reason': f'ストアに終了告知（{pat}）'}
        return {'alive': True, 'appId': best.get('trackId'), 'name': best.get('trackName'),
                'reason': ''}
    got = ', '.join(r.get('trackName', '') for r in results[:3]) or '該当なし'
    return {'alive': False, 'appId': None, 'name': None,
            'reason': f'検索結果に本タイトルが無い（{got}）'}


def inspect_ranking_pages():
    """ランキングページの構造をログに出す（パーサが0件になったときの調査用）。
    GAMES_INSPECT=1 で実行する。取得も解析もせず、素の HTML の形だけを見る。"""
    for label, url in (('AppMedia', APPMEDIA_URL), ('Game-i', GAMEI_URL)):
        print('=' * 70)
        print(f'[inspect] {label}: {url}')
        try:
            html = _http_text(url)
        except Exception as ex:
            print(f'  取得失敗: {ex}')
            continue
        print(f'  長さ: {len(html)}文字')
        for tag in ('table', 'tr', 'td', 'li', 'ol', 'ul', 'div', 'a'):
            print(f'  <{tag}> の数: {len(re.findall("(?i)<" + tag + r"[ >]", html))}')
        rows = re.findall(r'(?is)<tr[^>]*>(.*?)</tr>', html)
        print(f'  parse_rank_rows の抽出件数: {len(parse_rank_rows(html, 300))}')
        print(f'  <tr> ブロック数: {len(rows)}')
        for i, row in enumerate(rows[:4]):
            print(f'  --- tr[{i}] raw ---')
            print('  ' + row[:400].replace('\n', ' '))
            print(f'  --- tr[{i}] cells ---')
            print('  ' + repr([c.strip() for c in strip_tags(row).split(chr(10)) if c.strip()][:8]))
        # 行の組み方が tr/li でない場合の手がかりを出す
        n_app = len(re.findall(r'\./\?APP/', html))
        print(f'  "./?APP/" リンク数: {n_app}')
        i = html.find('link_page_passage')
        if i < 0:
            i = html.find('./?APP/')
        if i >= 0:
            print('  --- 1件目のアプリリンク周辺（前1200/後1800文字）---')
            print('  ' + html[max(0, i - 1200):i + 1800].replace('\n', ' '))
        # alt="アプリ名" の直前を見て、順位がどこに置かれているか調べる
        for m in list(re.finditer(r'alt="([^"]{2,40})"', html))[:3]:
            st = max(0, m.start() - 700)
            print(f'  --- alt="{m.group(1)}" の直前700文字 ---')
            print('  ' + html[st:m.start()].replace('\n', ' '))

def load_prev():
    if os.path.exists(OUT):
        try:
            return json.load(open(OUT, encoding='utf-8'))
        except Exception:
            pass
    return {}


def main():
    if os.environ.get('GAMES_INSPECT') == '1':
        inspect_ranking_pages()
        return
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    prev = load_prev()
    miss_state = dict(prev.get('missState', {}))    # {value: 連続未検出日数}
    app_ids = dict(prev.get('appIds', {}))          # {value: trackId}
    eos_prev = {e['value']: e for e in prev.get('suspect', prev.get('eos', []))
                if isinstance(e, dict) and 'value' in e}

    # ── ① セールスランキングを先に取る（プレイ中タイトルの順位付けにも使う） ──
    grossing, free, rank_sources = fetch_ranking()
    by_name, by_id = build_rank_index(grossing)
    print(f"[rank] 売上ランキング {len(grossing)}件 / 無料ランキング {len(free)}件"
          f" / 取得元: {rank_sources}")

    # ── ② プレイ中タイトルの生存確認 ──
    playing, suspect, checks = [], [], []
    for value, label, term in SEED:
        r = check_title(value, label, term, app_ids.get(value))
        time.sleep(SEARCH_SLEEP)
        if r['appId']:
            app_ids[value] = r['appId']
        rank = lookup_rank(by_name, by_id, app_ids.get(value), [value, label, r['name']])
        checks.append({'value': value, 'alive': r['alive'], 'rank': rank, 'reason': r['reason']})

        if r['alive'] is False and rank is not None:
            # 安全弁: 売上ランキングに載っているタイトルはサービス継続中で確実。
            # SEED の表記ゆれ等で照合に失敗しても、稼働中のゲームは消さない。
            print(f"[keep] 照合失敗だが売上{rank}位に在位 → 生存扱い: {label} — {r['reason']}")
            checks[-1]['alive'] = True
            checks[-1]['reason'] = f"照合失敗だが売上{rank}位に在位（{r['reason']}）"
            r['alive'] = True

        if r['alive'] is True:
            miss_state[value] = 0
            playing.append({'value': value, 'label': label, 'rank': rank})
        elif r['alive'] is False:
            miss_state[value] = miss_state.get(value, 0) + 1
            # ── 自動削除はしない ──
            # ストア名の変更や検索のあいまいさで、稼働中のタイトルを誤って
            # 消してしまう事故が実際に起きたため（モンギル：STAR DIVE など）、
            # プレイ中の一覧からは外さず「終了の可能性」として印を付けるだけにする。
            # 実際に消すかどうかは利用者が画面から手動で決める。
            playing.append({'value': value, 'label': label, 'rank': rank,
                            'sunsetting': True, 'missDays': miss_state[value],
                            'reason': r['reason']})
            if miss_state[value] >= GRACE_DAYS:
                suspect.append({'value': value, 'label': label,
                                'since': eos_prev.get(value, {}).get('since', today.strftime('%Y-%m-%d')),
                                'days': miss_state[value], 'reason': r['reason']})
                print(f"[warn] 終了の可能性(連続{miss_state[value]}回未検出): {label} — {r['reason']}")
            else:
                print(f"[warn] 未検出{miss_state[value]}回目: {label} — {r['reason']}")
        else:
            # 通信失敗 → 前回状態を維持して掲載継続（未検出カウントは進めない）
            playing.append({'value': value, 'label': label, 'rank': rank})

    # 再びストアで見つかれば missState が 0 に戻り、印も自然に外れる

    # ── ③ ランキング上位（新作の自動追加・サ終の自動消滅） ──
    seed_norms = {norm(v) for v, _, _ in SEED} | {norm(l) for _, l, _ in SEED}
    # プレイ中は自動で消さないので、人気一覧からの重複除外だけ行う
    trending, seen = [], set()
    for e in grossing + free:
        name = e['name']
        n = norm(name)
        if not n or n in seen:
            continue
        if any(n.startswith(s) or s.startswith(n) for s in seed_norms if len(s) >= 2):
            continue  # プレイ中と重複
        if any(k.lower() in name.lower() for k in EXCLUDE_KEYWORDS):
            continue  # 非ガチャ
        seen.add(n)
        item = {'value': name, 'label': name,
                'rank': lookup_rank(by_name, by_id, e.get('id'), [name])}
        if e.get('category'):
            item['category'] = e['category']
        trending.append(item)

    ranked = sum(1 for g in playing if g.get('rank'))
    out = {
        'updated': today.strftime('%Y-%m-%d %H:%M JST'),
        'rankSources': rank_sources,
        'rankingSize': len(grossing),
        'playing': playing,
        'trending': trending[:200],
        'suspect': suspect,          # 終了の可能性（自動削除はせず印だけ付ける）
        'appIds': app_ids,
        'missState': miss_state,
        'checks': checks,
    }
    if os.environ.get('GAMES_DRY_RUN') == '1':
        print(json.dumps({k: out[k] for k in ('updated', 'suspect', 'checks')},
                         ensure_ascii=False, indent=1))
        return
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"[done] playing={len(playing)}（セルラン付き {ranked}件） "
          f"trending={len(out['trending'])} 終了の可能性={len(suspect)}")
    if suspect:
        print('[done] 終了の可能性（自動削除はしません。画面から手動で削除してください）: '
              + ', '.join(e['label'] for e in suspect))


if __name__ == '__main__':
    main()
