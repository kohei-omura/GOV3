# GACHA ORACLE

ガチャを引く日と時刻を、暦（六曜・旧暦・二十四節気・暦注下段）と各種占術から
割り出す PWA。GitHub Pages でそのまま配信される。

## 構成

```
index.html        アプリ本体（単一ファイル。暦エンジンも占術もこの中）
manifest.json     PWA の定義
sw.js             Service Worker（オフライン動作・キャッシュ）

assets/           アイコン
data/             自動更新されるデータ
  games.json        プレイ中／人気タイトルとセルラン（毎日更新）
  calendar.json     六曜・月齢・旧暦の実測値（毎週更新）
scripts/          data/ を生成するスクリプト
  update_games.py    App Store・AppMedia・Game-i から取得
  update_calendar.py 実測暦を取得
tests/            回帰テスト（ネットワーク不要）
  test_almanac.mjs   暦エンジン ↔ 実測暦・公開暦の突き合わせ
  test_ui.mjs        画面まわり（プレイ中一覧の編集・保存結果の扱い）
  test_games.py      ゲームリスト更新ロジック
```

`index.html` / `manifest.json` / `sw.js` は配信の都合で直下に置く必要がある
（Service Worker はスコープが置き場所で決まるため）。

## テスト

```sh
node tests/test_almanac.mjs
node tests/test_ui.mjs
python3 tests/test_games.py
```

## データの自動更新

`.github/workflows/` の 2 つで回している。どちらもテストを通してからコミットする。

| ワークフロー | 実行 | 生成物 |
|---|---|---|
| `update-games.yml` | 毎日 6:00 JST | `data/games.json` |
| `update-calendar.yml` | 毎週月曜 5:00 JST | `data/calendar.json` |

## 変更するときの注意

- **暦やスコアの計算、保存する結果の項目を変えたら `index.html` の `CALC_REV` を上げる。**
  鑑定結果は端末の localStorage に保存され、同じ日・同じ条件なら再利用されるため、
  上げないと直す前の結果がその日いっぱい出続ける。
- **配信ファイルを増減したら `sw.js` の `CACHE_VERSION` を上げる。**
- 暦注の表を直したら、公開暦の実データと突き合わせて `tests/test_almanac.mjs` に
  ケースを足す。過去に十死日・狼藉日・地火日で取り違えている。
