# 大トレンドブレイク検出 — Pine Script → Python バックテスター

TradingView の Pine Script v5 インジケーター
**「大トレンドブレイク検出（ライン強調のみ）」** を Python に**完全等価**で移植し、
過去 10 年間のヒストリカルデータ（`XAUUSD / XAGUSD / NAS100 / BTC / GBPJPY` …）に対する
バックテスト + 多角的分析 + パラメータ最適化を行うためのツールです。

---

## 仮説

> 「長期間意識されていた高値・安値を、長期間触れていない状態から実体ブレイクしたとき、
>  大トレンドが発生しやすい」

| 用語 | 意味 |
| --- | --- |
| 長期ライン | 過去 `lookback` 本（既定 5000 本）の高値/安値 |
| 中期ライン | 過去 `lookback_3m` 本（既定 480 本）の高値/安値 |
| 直近接触除外 | 直近 `exclude_recent` 本（既定 760 本）に水準が触れていないこと |
| 実体ブレイク | バー終値（`close`）が水準を上抜け／下抜け（ヒゲ抜け不可） |

詳細は `docs/design_document.md` を参照。

---

## ✅ 絶対条件への対応

| 要件 | 対応 |
| --- | --- |
| Pine Script と完全一致 | `pine_compat_mode="literal"` で原 Pine と数値・boolean 完全一致を 9 ケースのテストで保証 |
| 未来データ参照禁止 | 全 rolling は過去側にのみ。`shift(1)` 厳密過去のみ参照 |
| リペイント禁止 | 全データ評価 vs 切詰め評価が完全一致するテストで保証 |
| datetime 自動判定 | ISO-8601 / `YYYY/MM/DD` / unix(s/ms/ns) 自動検出 |
| 高速化 | pandas rolling によるベクトル化 + ループ実装と完全一致確認 |
| 例外処理強化 | `[ERR-PARAM]` `[ERR-DATA]` `[ERR-DATETIME]` `[ERR-IO]` のエラーコード体系 |
| GUI | tkinter（ヘッドレス時 CLI フォールバック） |
| 検証ログ保存 | `logs/run_<timestamp>.log` |
| CSV 出力 | trades / equity / 9 種類の breakdown |
| チャート保存 | 価格+ライン+シグナル / Equity+DD / 分布 |

---

## ⚠️ Pine Script 仕様上の重要な発見

原 Pine の以下のループ：

```pine
for i = lookback - 1 to 0
    h = high[i]
    highLevel := na(highLevel) or h > highLevel ? h : highLevel
```

は **i=0（現在バー）を含む** ため、`highLevel = max(high[0..lookback-1])` には現バー高値が含まれます。シグナル条件は `close > highLevel` ですが、OHLC の性質上 `close ≤ high[0] ≤ highLevel` が常に成立し、**`close > highLevel` は数学的にほぼ発火しません**。

これは原 Pine ロジックの不具合と判断しました。本ポートでは 2 モードを提供：

| モード | 水準計算 | 用途 |
| --- | --- | --- |
| `literal`  | `max/min(high[0..lookback-1])` 現在バー込み | 厳密な Pine 一致確認用（実シグナル無し） |
| `intended` | `max/min(high[1..lookback])` 現在バー除外 | 既定。ユーザの「実体ブレイク」意図に最も近い |

詳細は `docs/design_document.md §1.2`。

---

## インストール

Python 3.10+。

```bash
pip install -r requirements.txt
# Linux で GUI を使う場合は tkinter
sudo apt-get install -y python3-tk
```

主要依存: `numpy / pandas / matplotlib / scipy / tqdm`。
GUI: `tkinter` (標準ライブラリ + linux 別途)。
テスト: `pytest`。

---

## ディレクトリ構成

```
.
├── README.md
├── requirements.txt
├── main.py                      # CLI / GUI エントリーポイント
├── configs/
│   └── default.json             # JSON 設定例
├── docs/
│   └── design_document.md       # Pine Script 解析 & 設計書
├── src/
│   ├── config.py                # IndicatorConfig / BacktestConfig / RunConfig
│   ├── indicator.py             # Pine 完全等価インジケーター（reference + vectorised）
│   ├── data_loader.py           # CSV → DataFrame, datetime 自動判定
│   ├── backtest.py              # 1 バー 1 ステップのリペイント禁止バックテスト
│   ├── metrics.py               # 勝率 / PF / DD / Sharpe / Sortino / Calmar
│   ├── analysis.py              # 通貨/方向/セッション/曜日/時刻/年/ボラ/ダマシ/パラメータ別分析
│   ├── plotter.py               # 価格+ライン+シグナル / Equity / 分布
│   ├── optimizer.py             # グリッド + ランダムサーチ（並列）
│   ├── logger.py                # 実行ログ保存
│   ├── runner.py                # 1 CSV → バックテスト → 全アーティファクト出力
│   └── gui.py                   # tkinter GUI
├── tests/
│   ├── test_indicator.py        # Pine 等価性 / 未来リーク / 手作業検算 / warm-up
│   ├── test_data_loader.py      # ISO/unix s/ms 自動判定 / OHLC 検証 / dedupe
│   ├── test_backtest_metrics.py # E2E / no-repaint / メトリクス
│   └── test_e2e.py              # CSV → 全アーティファクト出力 smoke
├── data/                        # ユーザーの OHLCV CSV
├── results/                     # バックテスト出力先（自動作成）
└── logs/                        # 実行ログ
```

---

## 入力 CSV 形式

```
datetime,open,high,low,close,volume
2015-01-01 00:00:00,1.0123,1.0145,1.0120,1.0140,1234
...
```

**自動判定対応**:
- 列名は大文字小文字無視。`datetime` `time` `timestamp` `<DATE>+<TIME>` 等を解釈。
- 値は ISO-8601, `YYYY-MM-DD HH:MM:SS`, `YYYY/MM/DD`, unix(s/ms/ns) すべて受理。
- ファイル名から自動的にシンボル推論：`XAUUSD_h1_2014-2024.csv → XAUUSD`。
- ピップサイズも自動推論：JPY-cross→0.01 / XAUUSD→0.1 / XAGUSD→0.01 / BTC→1 / NAS100→1 / FX-major→0.0001。

---

## 使い方

### GUI

```bash
python main.py --gui
```

- `DISPLAY` がない環境では自動で CLI フォールバック。

### 1 通貨ペアのバックテスト

```bash
python main.py --csv data/XAUUSD_1h.csv --pine-compat-mode intended
```

### 5 通貨ペア一括実行（10 年データ想定）

```bash
python main.py \
    --csv data/XAUUSD_1h.csv data/XAGUSD_1h.csv \
          data/NAS100_1h.csv data/BTCUSD_1h.csv data/GBPJPY_1h.csv \
    --lookback 5000 --exclude-recent 760 \
    --lookback-3m 480 --exclude-recent-3m 120 \
    --direction both --tp-rr 2.0 --risk-pct 1.0
```

### ★ ディレクトリ内の **全通貨自動検証**（推奨）

ヒストリカルデータをまとめてフォルダ単位で投入する場合、`--data-dir` 一発で再帰的に
**全 CSV を発見 → 個別バックテスト → クロスシンボル比較表** までを自動で行います。

```bash
# フォルダ内の全 CSV を再帰的に検証
python main.py --data-dir data/

# ZIP も自動展開してから検証
python main.py --data-dir data/ --extract-zip

# 例: H1 タイムフレームの CSV だけに限定
python main.py --data-dir data/ --data-pattern "**/*_H1.csv"

# ファイル名から自動推論されたシンボルが「XAUUSD/GBPJPY/...」に
# 対応しないときは --pip-size を指定してください（FX 以外）
```

実行後の出力:

```
results/_batch_<UTC>/
├── cross_symbol.csv         # ★ 全通貨横断サマリ（リターン降順）
├── batch_config.json        # 実行時の全パラメータ
├── XAUUSD_<UTC>/
│   ├── trades.csv  equity.csv  summary.json
│   ├── breakdown_*.csv      # 9 種類の集計
│   └── chart_*.png          # 価格+ライン+シグナル / Equity+DD / R 分布
├── GBPJPY_<UTC>/...
├── NAS100_<UTC>/...
└── ...
```

`cross_symbol.csv` 例：

```
symbol  rows  n_trades win_rate profit_factor max_drawdown_pct total_return_pct sharpe expectancy_r
NAS100  6000         4   75.00%         5.960           -1.00%            5.06%  2.424        1.250
XAGUSD  6000         3   66.67%         4.000           -2.60%            3.00%  1.373        1.000
...
```

各 CSV 別に `results/<SYMBOL>_<timestamp>/` フォルダが作成され：
- `trades.csv` …… エントリー履歴（27 列）
- `equity.csv` …… 各バーの口座残高
- `breakdown_*.csv` …… 通貨/方向/セッション/曜日/時刻/年/ボラ/ダマシ/パラメータ別の集計
- `chart_price.png` …… 価格+ライン+シグナル
- `chart_equity.png` …… 残高曲線+ドローダウン
- `chart_distribution.png` …… R 倍数ヒストグラム + 累積 PnL
- `summary.json` …… 全結果の機械可読サマリ

### パラメータ最適化（グリッド）

```bash
python main.py --csv data/XAUUSD_1h.csv --grid \
    --grid-lookback 3000 4000 5000 6000 \
    --grid-exclude  500 760 1200 \
    --grid-lookback-3m 240 480 720 \
    --grid-exclude-3m 60 120 240 \
    --workers 8 --min-trades 10
```

評価関数は既定で `PF + 0.5*WinRate − 0.5*|MaxDD%|`（`src/optimizer.py` で差替可）。
`results/grid_<SYMBOL>.csv` に全組合せがスコア順で保存されます。

---

## エントリー履歴 CSV のスキーマ

```
trade_id, symbol, direction, level_kind,
signal_time, entry_time, entry_price, sl, tp,
exit_time, exit_price, exit_reason, bars_held,
pnl_price, pnl_pips, pnl_pct, pnl_money, r_multiple,
atr_at_entry, session, weekday, hour_utc, is_fakeout,
lookback, exclude_recent, lookback_3m, exclude_recent_3m
```

- `is_fakeout`: SL に 5 バー以内で当たったトレード（ダマシ判定）。
- `session`: `asia` / `europe` / `ny`（UTC ベース）。

---

## バックテスト仕様（リペイント禁止）

1. インジケーターはデータ全体に対して**一括計算**（過去側 rolling のみ）。
2. シグナルはバー**終値**で確定。約定は既定で**翌バーの始値**（`entry_fill="next_open"`）。
3. SL/TP の hit は約定バーより**後**のバーの High/Low のみで判定。同バーで両方 hit したら SL を優先（保守的）。
4. ポジション保有中は新規シグナル無視（`one_position_only=True`）。
5. 終端でオープンポジは終値クローズ（`exit_reason="eod"`）。

設定一覧は `src/config.py` の `BacktestConfig` を参照。

---

## テスト

```bash
python -m pytest tests/ -v
```

27 ケース全通過：

- Pine 完全等価（vectorised vs reference）
- 未来データ参照禁止
- リペイント禁止（全データ vs 切詰めで一致）
- 手作業検算
- ATR 数値検証
- パラメータ妥当性
- CSV 自動判定（ISO / unix s / unix ms / 列名揺らぎ / OHLC 整合性 / dedupe）
- バックテスト E2E（trades CSV / equity CSV / breakdown CSV / 3 種類のチャート / summary JSON）
- メトリクス数値検証（PF, DD, expectancy）
- バッチランナー: ディレクトリ走査 / 再帰ディスカバリ / クロスシンボル比較

---

## ライセンス

ユーザー個人プロジェクトとして MIT 相当で提供。
