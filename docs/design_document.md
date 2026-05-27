# 大トレンドブレイク検出 — Pine Script → Python 変換設計書

本ドキュメントは、ユーザー提供の Pine Script v5 インジケーター
「**大トレンドブレイク検出（ライン強調のみ）**」を Python に**完全等価**で移植し、
過去検証（バックテスト）プラットフォームを構築するための設計書である。

---

## 0. 仮説と用語

> *「長期間意識されていた高値・安値を、長期間触れていない状態から実体ブレイクしたとき、大トレンドが発生しやすい」*

| 用語 | 意味 |
| --- | --- |
| 長期ライン | 過去 `lookback` 本の高値/安値（既定 5000 本） |
| 中期ライン | 過去 `lookback_3m` 本の高値/安値（既定 480 本） |
| 直近接触除外期間 | 直近 `exclude_recent` 本のあいだ価格が水準に届いていないこと（既定 760 本） |
| 実体ブレイク | バー終値（`close`）が水準を抜いたこと（ヒゲ抜けは無効） |

---

## 1. Pine Script ロジック分解

### 1.1 入力パラメータ

```pine
lookback           = input.int(5000, "探す期間（過去バー本数 / 長期）")
exclude_recent     = input.int( 760, "直近を無視する期間（本 / 長期）")
lookback_3m        = input.int( 480, "探す期間（過去バー本数 / 中期）")
exclude_recent_3m  = input.int( 120, "直近を無視する期間（本 / 中期）")
```

### 1.2 水準ライン計算ループ

```pine
var float highLevel = na
var float lowLevel  = na
highLevel := na          // ★ 毎バー na にリセット
lowLevel  := na

for i = lookback - 1 to 0
    h = high[i]
    l = low[i]
    highLevel := na(highLevel) or h > highLevel ? h : highLevel
    lowLevel  := na(lowLevel)  or l < lowLevel  ? l : lowLevel
```

これは **「現在バーから過去 `lookback` 本（`[0]`..`[lookback-1]`）における最大 `high` と最小 `low`」** を求める処理に等しい。

数式として：

\[
\mathrm{highLevel}_t = \max_{k=0}^{\mathrm{lookback}-1} \mathrm{high}_{t-k},\qquad
\mathrm{lowLevel}_t  = \min_{k=0}^{\mathrm{lookback}-1} \mathrm{low}_{t-k}
\]

中期 (`*_3m`) も同形。

### 1.3 直近接触除外条件

```pine
recentHighTouch = ta.highest(high[1], exclude_recent) >= highLevel
recentLowTouch  = ta.lowest (low[1],  exclude_recent) <= lowLevel
noRecentHighTouch = not recentHighTouch
noRecentLowTouch  = not recentLowTouch
```

`ta.highest(series[1], n)` は **「1 本前を起点に過去 `n` 本のローソクの最大値」**。
すなわち `max(high[1], high[2], …, high[n])`。

これにより、現在バーの動き（=ブレイク）は除外しつつ、直近 `n` 本に**水準と等しい高値が存在しない**ことを要求する。

> ### ⚠️ Pine Script 仕様上の重要な注意点（必読）
>
> §1.2 のループは `for i = lookback - 1 to 0` と書かれており **i=0 (現在バー) を含む**。
> したがって `highLevel = max(high[0..lookback-1])` には**現在バーの高値**が含まれる。
> 一方シグナル条件は `close > highLevel`。OHLC の関係上 `close ≤ high[0] ≤ highLevel` が常に成立するため、
> **`close > highLevel` は数学的にほぼ発火しない**。
> （ショート側 `close < lowLevel` も同様）
>
> これは原 Pine Script のロジック上の不具合と判断される。
> 本 Python 移植では「Pine 完全一致」を保ちつつ実用的な検証も可能にするため、`pine_compat_mode` で 2 モードを切替可能にする：
>
> | モード | 水準計算 | 用途 |
> | --- | --- | --- |
> | `literal`  | `max/min(high[0..lookback-1])` 現在バー込 | 厳密な Pine 一致確認用（実シグナル無し） |
> | `intended` | `max/min(high[1..lookback])` 現在バー除外 | 既定。ユーザの「実体ブレイク」意図に最も近い |
>
> どちらのモードでも *直近接触除外* `ta.highest(high[1], n)` の挙動は完全一致。

\[
\text{noRecentHighTouch}_t \;\Leftrightarrow\;
\max_{k=1}^{n} \mathrm{high}_{t-k} < \mathrm{highLevel}_t
\]

<br>

> **重要なセマンティクス**:
>
> `highLevel` は「lookback 全体」の max なので、直近 `n` 本に等高値がある場合は
> `recentHighTouch` が必然的に true になる。よって実質的に
> **「水準は `[exclude_recent .. lookback-1]` の古い領域から来た値であり、
> 直近の `[1..exclude_recent]` 本では一度も到達していない」**
> という条件になる（`>=` 比較なので**狭義に**未到達）。
>
> 本実装はこの仕様を厳密に再現する。

### 1.4 ブレイク条件

```pine
longCond  = close > highLevel and noRecentHighTouch
shortCond = close < lowLevel  and noRecentLowTouch
```

- ロング: 終値が長期高値水準を**上抜け**かつ直近未接触
- ショート: 終値が長期安値水準を**下抜け**かつ直近未接触

中期（`longCond3m` / `shortCond3m`）も同形。

### 1.5 表示
プロットされる 5 系列（高値/安値の長期＋中期、中期中央線）を Python では Matplotlib のラインオーバレイで再現する。

---

## 2. 等価性検証（Pine ↔ Python）

| Pine Script | Python 実装方針 |
| --- | --- |
| `for i = N-1 to 0` の max ループ | `pandas.Series.rolling(window=N, min_periods=1).max()` （現在バーを含む） |
| `ta.highest(high[1], n)` | `series.shift(1).rolling(window=n, min_periods=1).max()` |
| `ta.lowest(low[1], n)`  | `series.shift(1).rolling(window=n, min_periods=1).min()` |
| `na`（未確定値） | `NaN` を伝播。比較は `False` 返却（pandas デフォルト） |

#### ウォームアップ
- 長期ラインは少なくとも `lookback` 本のヒストリーが必要。
- それ未満のバーは Pine と同様にライン値が存在するが、シグナルは `recentHighTouch` 判定が成立しない**真にバー数が `exclude_recent+1` 以上のとき**のみ点灯する。
- 厳密な完全一致のため、Python 側では `bars_available < lookback` のバーではシグナルを `False` とする保守的フィルタを設ける（オプション、デフォルト on）。

#### NaN ハンドリング
Pine の `na(x) or x > level` は実質「初回は受け入れる」処理。
`rolling(min_periods=1).max()` も同等の挙動。

---

## 3. 未来データ参照禁止 / リペイント禁止

| 観点 | 対策 |
| --- | --- |
| 未来データ参照 | すべての rolling は **過去側にだけ** ウィンドウ。`shift(1)` は厳密に過去。`close[i]` 比較は当該バー時点の確定値のみ。 |
| 信号発火タイミング | バー**終値で確定**。 |
| エントリー約定 | 翌バー始値（`open[t+1]`）で約定する保守仕様（既定）。`fill_on=close` にすれば当該バー終値で約定（Pine と同列）。 |
| リペイント検査 | テストで「過去データを 1 本ずつ追加した逐次評価」と「全データ一括評価」が**完全一致する**ことを確認。 |

---

## 4. システム・アーキテクチャ

```
trend_break_backtester/
├── src/
│   ├── __init__.py
│   ├── indicator.py    # Pine 完全等価のインジケーター（ベクトル化）
│   ├── data_loader.py  # CSV → DataFrame, datetime 自動判定, 整合性検証
│   ├── backtest.py     # シグナル → トレード履歴, リペイント禁止
│   ├── metrics.py      # 勝率/PF/DD/RR/期待値/Sharpe/Sortino/CAGR
│   ├── analysis.py     # 通貨別/時間帯/ボラ/ダマシ分析
│   ├── optimizer.py    # グリッド & ランダム探索（並列）
│   ├── plotter.py      # 価格+ライン+シグナル, Equity, DD
│   ├── logger.py       # 実行ログ保存
│   ├── config.py       # 設定 dataclass
│   └── gui.py          # tkinter GUI（ヘッドレス時 CLI fallback）
├── tests/              # ユニットテスト（Pine 等価性 / リペイント / メトリクス）
├── data/               # ユーザー CSV
├── results/            # 出力 CSV / PNG
├── logs/               # 検証ログ
├── configs/            # JSON 設定例
├── main.py             # CLI / GUI エントリ
├── requirements.txt
└── README.md
```

---

## 5. データ仕様

### 5.1 入力 CSV

```
datetime,open,high,low,close,volume
2014-01-01 00:00:00,1.0123,1.0145,1.0120,1.0140,1234
...
```

| 項目 | 型 | 備考 |
| --- | --- | --- |
| datetime | str/ISO8601 | 自動パーサで `datetime.datetime` に変換。`unix`/`epoch_ms` も自動判定。 |
| open/high/low/close | float | OHLC 整合性チェック（`high>=max(open,close)` 等）。違反は警告 + 行除外オプション。 |
| volume | float | 任意。欠損可。 |

### 5.2 自動判定ロジック (`data_loader.detect_datetime_column`)

1. ヘッダ大文字小文字を正規化
2. 候補列名: `datetime`, `date`, `time`, `timestamp`, `Date`, `<DATE>`, `<TIME>` 等
3. ISO8601 / `YYYY-MM-DD HH:MM:SS` / `YYYY/MM/DD` / unix(s) / unix(ms) を順に試行
4. すべて失敗時は `ValueError` で `[ERR-DATETIME]` を投げる
5. UTC 仮定 + `--tz` で変換可能

---

## 6. バックテスト仕様

### 6.1 トレード生成
| 設定 | 既定 | 説明 |
| --- | --- | --- |
| `entry_fill` | `next_open` | `next_open` または `signal_close` |
| `direction` | `both` | `long_only` / `short_only` / `both` |
| `level_kind` | `long` | `long` / `mid` / `confluence`（長期・中期同方向） |
| `sl_mode` | `atr` | `atr`(N×ATR) / `fixed_pct` / `signal_bar`（シグナルバーの反対側） |
| `tp_mode` | `rr` | `rr`(R 倍数) / `atr` / `none` |
| `rr_multiple` | `2.0` | TP = RR×SL |
| `trailing` | `off` | `off` / `chandelier` |
| `time_exit_bars` | `0` | 0 で無効、>0 で N バー経過時クローズ |
| `cost_pips` | `0.0` | スプレッド/手数料相当（pips） |
| `slippage_pips` | `0.0` | スリッページ |

### 6.2 ループ設計（リペイント禁止）

- バーごとに「**前足終値で確定したシグナル**」のみ参照可
- ポジション保有中は新規シグナルを無視（オプションで多重ポジ可）
- 約定価格・SL/TP は entry バーが決まった瞬間に確定し、以降不変

### 6.3 出力 CSV (`results/trades_<symbol>_<ts>.csv`)
```
trade_id,symbol,direction,signal_time,entry_time,entry_price,sl,tp,
exit_time,exit_price,exit_reason,bars_held,pnl_pips,pnl_pct,r_multiple,
volatility_atr14,session,is_fakeout,level_kind,
lookback,exclude_recent,lookback_3m,exclude_recent_3m
```

---

## 7. メトリクス

| 指標 | 式 |
| --- | --- |
| 勝率 (Win Rate) | wins / total |
| PF (Profit Factor) | Σ(profits) / |Σ(losses)| |
| 期待値 (Expectancy) | 平均 R |
| 最大DD (Max Drawdown) | min(equity - cummax(equity)) / cummax(equity) |
| 平均RR | 平均(profit/risk) |
| Sharpe / Sortino | リターンの平均/標準偏差（or 下方標準偏差）×√N |
| CAGR | 任意（`equity_initial` 設定時） |

---

## 8. 分析モジュール

1. **通貨別分析**: シンボルごとに上記メトリクスを集計
2. **ダマシ分析**: シグナル発火後 `K` バー以内に逆方向にブレイクし戻る回数 / SL 直撃比率
3. **時間帯分析**: アジア / 欧州 / NY セッション別、曜日別、月別
4. **ボラティリティ分析**: ATR 分位（低・中・高）別パフォーマンス

---

## 9. パラメータ最適化

- グリッドサーチ + ランダムサーチ
- `multiprocessing.Pool` による並列
- 評価関数は **PF + 0.5 × WinRate − 0.5 × MaxDD%**（カスタム可能）
- **ウォークフォワード分析**: 学習期間 → テスト期間 を時系列でずらす（任意）
- 過剰最適化抑制: トレード数 < `min_trades` の組合せは除外

---

## 10. GUI（tkinter）

- データセット選択（複数可、シンボル名は CSV ファイル名から自動推論）
- パラメータ入力（長期/中期/除外）
- バックテスト・最適化の実行ボタン
- ログ・結果テーブルのリアルタイム表示
- ヘッドレス環境（`DISPLAY` 不存在）では CLI に自動フォールバック

---

## 11. ロギング & 例外処理

- すべての主要関数は `try/except` でラップし、`logging` モジュールで `INFO/WARN/ERROR` を分離
- すべての実行で `logs/run_<timestamp>.log` を生成
- 入力データ異常 → 行スキップ + 集計レポート
- パラメータ異常 → 即時エラー（`[ERR-PARAM]`）
- ファイル I/O 異常 → 即時エラー（`[ERR-IO]`）

---

## 12. 受け入れテスト一覧

| テスト | 内容 |
| --- | --- |
| `test_indicator_match_pine` | 手作業計算した小データで `highLevel/lowLevel/longCond/shortCond` が一致 |
| `test_no_repaint`           | 一括評価 vs 1 本ずつ追加評価が完全一致 |
| `test_no_future_leak`       | 任意の時刻 t のシグナルが t 以前のデータのみで決まる |
| `test_metrics`              | 既知サンプルでの勝率/PF/DD/期待値の数値一致 |
| `test_backtest_e2e`         | 合成データで end-to-end が落ちず、CSV/PNG が出る |
| `test_datetime_detection`   | ISO/unix/unix_ms すべて正しく解釈 |

---

## 13. 段階的実装計画

1. **Phase 1**: `indicator.py` + 等価性ユニットテスト（最重要）
2. **Phase 2**: `data_loader.py` + `backtest.py` + `metrics.py`
3. **Phase 3**: `analysis.py` + `plotter.py` + `logger.py`
4. **Phase 4**: `optimizer.py`（並列）
5. **Phase 5**: `gui.py` + `main.py` + README + E2E スモークテスト

各フェーズで commit & push & PR 更新を行う。
