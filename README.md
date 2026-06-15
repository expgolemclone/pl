# pl

XBRL損益計算書の推移を可視化する静的HTMLジェネレーター。

EDINET XBRLデータをSQLiteから読み込み、インタラクティブなダークテーマのHTMLチャートを出力する。

## 公開レポート

GitHub Pages: <https://expgolemclone.github.io/pl/>

- [6142 富士精工](https://expgolemclone.github.io/pl/reports/6142_pl_trends.html)
- [7175 今村証券](https://expgolemclone.github.io/pl/reports/7175_pl_trends.html)
- [4776 サイボウズ](https://expgolemclone.github.io/pl/reports/4776_pl_trends.html)
- [8473 SBI HD](https://expgolemclone.github.io/pl/reports/8473_pl_trends.html)
- [8595 ジャフコグループ](https://expgolemclone.github.io/pl/reports/8595_pl_trends.html)

## 機能

- **複数系列のオーバーレイ** ― テーブルの行をクリックして任意のPL項目を重ね描き
- **CAGR forecast** ― 年平均成長率に基づく2期先の予測線（破線）
- **スパークライン** ― 各項目のミニ推移グラフをテーブル内に表示
- **単位切替** ― 円 / 百万円 / 億円
- **連結・個別の自動選択** ― `--scope auto` で連結優先、個別フォールバック
- **レスポンシブ** ― モバイル〜デスクトップ対応
- **Playwrightによる検証・スクリーンショット** ― CIでの描画確認に利用

## 必要要件

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/)

## セットアップ

```sh
uv sync
uv sync --group dev   # Playwrightによる検証を行う場合
```

## 使い方

```sh
# 直近10期の損益計算書推移を出力し、Playwrightで10分間表示
uv run pl-trends 4776

# 期間数を指定
uv run pl-trends 4776 --periods 5

# 出力先を指定
uv run pl-trends 4776 --output var/reports/4776.html

# 個別財務のみ
uv run pl-trends 4776 --scope non_consolidated

# Playwrightを無効化してHTMLのみ生成
uv run pl-trends 4776 --no-open-with-playwright

# DBパスを明示的に指定
uv run pl-trends 4776 --db /path/to/stocks.db

# スクリーンショットを保存
uv run pl-trends 4776 --playwright-screenshot var/reports/4776.png
```

実行例:

```
$ uv run pl-trends 4776 --periods 5
Wrote var/reports/4776_pl_trends.html
4776 サイボウズ: 5 periods, 45 PL items

$ uv run pl-trends 7203 --periods 3
Wrote var/reports/7203_pl_trends.html
7203 トヨタ自動車: 3 periods, 21 PL items

$ uv run pl-trends 7203 --scope non_consolidated
Wrote var/reports/7203_pl_trends.html
7203 トヨタ自動車: 10 periods, 18 PL items
```

## CLIオプション

```
usage: pl-trends [-h] --db DB [--periods PERIODS] [--source SOURCE]
                 [--scope {auto,consolidated,non_consolidated}]
                 [--output OUTPUT] [--open-with-playwright]
                 [--playwright-screenshot PLAYWRIGHT_SCREENSHOT]
                 [--playwright-headed]
                 [--playwright-hold-ms PLAYWRIGHT_HOLD_MS]
                 [--playwright-browser-executable PLAYWRIGHT_BROWSER_EXECUTABLE]
                 [--playwright-timeout-ms PLAYWRIGHT_TIMEOUT_MS]
                 ticker
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `ticker` | （必須） | 銘柄コード |
| `--db` | `../stock_db/var/db/stocks.db` | SQLiteデータベースのパス |
| `--periods` | `10` | 取得する直近期間数 |
| `--source` | `edinet_xbrl` | データソースコード |
| `--scope` | `auto` | `auto` / `consolidated` / `non_consolidated` |
| `--output` | `var/reports/{TICKER}_pl_trends.html` | HTML出力パス |
| `--open-with-playwright` | `true` | PlaywrightでHTMLを開いて描画を検証（`--no-open-with-playwright` で無効化） |
| `--playwright-screenshot` | — | スクリーンショット保存パス |
| `--playwright-headed` | `true` | ブラウザを可視状態で起動 |
| `--playwright-hold-ms` | `600000`（10分） | 検証後にページを開いたままにする時間（ms） |
| `--playwright-browser-executable` | — | Chromium/Chrome実行ファイルのパス |
| `--playwright-timeout-ms` | `10000` | Playwrightのタイムアウト（ms） |

## テスト

```
$ uv run pytest
19 passed in 0.21s
```

## プロジェクト構成

```
src/pl/
  __init__.py
  pl_trends.py      # データ取得・HTML生成・CLI
tests/
  test_pl_trends.py # pytestテスト
```
