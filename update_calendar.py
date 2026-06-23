#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GACHA ORACLE 暦データ自動更新スクリプト
========================================
ajnet.ne.jp の暦カレンダーから「六曜・月齢・旧暦」を取得し calendar.json を生成。
GitHub Actions で定期実行 → index.html が起動時に読み込み、内蔵の較正計算より
優先して使う。取得失敗・範囲外日は index.html 内蔵の較正計算へ自動フォールバック。

年月指定: フォームPOST（yy / mm / send=変更）。EUC-JP。
"""
import urllib.request, urllib.parse, re, json, datetime, sys

CAL_URL = ("https://www.ajnet.ne.jp/diary_f/"
           "?ohGmI01LrhInI9dh0n9433nHyCnnmTYJSZrkYzAGNqVw3XS8nNRJcIybHViQAayndyWtJjF7IP7aGnHOX3ExN0cE1Yt9BrRoGavGNE1RjYQuPqnkjmFC1kQFVP9NInI9")
UA = {'User-Agent': 'Mozilla/5.0 (GachaOracle CalendarUpdater)'}
OUT = 'calendar.json'
MONTHS_AHEAD = 6   # 今月から何ヶ月先まで取得するか

def fetch_month(year, month):
    """指定年月をPOST取得しパース → {'YYYY-MM-DD': {rokuyo, moonAge, lunar}}"""
    data = urllib.parse.urlencode({'yy': str(year), 'mm': str(month), 'send': '変更'}).encode('euc-jp')
    req = urllib.request.Request(CAL_URL, data=data, headers=UA)
    html = urllib.request.urlopen(req, timeout=30).read().decode('euc-jp', errors='replace')

    result = {}
    # セルは <b>(&nbsp;)?DD</b> を境に並ぶ。各本文に 六曜 / 旧暦M/D / 月齢X.X が含まれる
    cells = re.split(r'<b>(?:&nbsp;)?(\d{1,2})</b>', html)
    for i in range(1, len(cells) - 1, 2):
        try:
            day = int(cells[i])
        except ValueError:
            continue
        if not (1 <= day <= 31):
            continue
        body = cells[i + 1]
        rk = re.search(r'(先勝|友引|先負|仏滅|大安|赤口)', body)
        ml = re.search(r'旧暦&nbsp;(\d+)/(\d+)', body)
        mm = re.search(r'月齢&nbsp;([\d.]+)', body)
        if not (rk and ml and mm):
            continue
        key = f"{year:04d}-{month:02d}-{day:02d}"
        result[key] = {
            'rokuyo': rk.group(1),
            'moonAge': float(mm.group(1)),
            'lunar': f"{ml.group(1)}/{ml.group(2)}",
        }
    return result

def main():
    today = datetime.date.today()
    data = {}
    ok = 0
    for off in range(MONTHS_AHEAD):
        y = today.year + (today.month - 1 + off) // 12
        m = (today.month - 1 + off) % 12 + 1
        try:
            md = fetch_month(y, m)
            if len(md) >= 28:          # 1ヶ月ほぼ全日取れた時のみ採用
                data.update(md)
                ok += 1
                print(f"[ok] {y}-{m:02d}: {len(md)}日分", file=sys.stderr)
            else:
                print(f"[warn] {y}-{m:02d}: {len(md)}日のみ（構造変化の疑い）", file=sys.stderr)
        except Exception as ex:
            print(f"[warn] {y}-{m:02d} fetch failed: {ex}", file=sys.stderr)

    if ok == 0:
        print("[error] 取得失敗。既存 calendar.json を維持して終了。", file=sys.stderr)
        sys.exit(0)

    out = {
        'updated': datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M JST'),
        'source': 'ajnet.ne.jp',
        'days': data,
    }
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"[done] {ok}ヶ月 / {len(data)}日分を {OUT} に保存")

if __name__ == '__main__':
    main()
