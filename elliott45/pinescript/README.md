# Elliott Wave 4 → 5 — TradingView Pine v5 ポート

`elliott45/` の Python 実装と **完全に同じロジック** で動く TradingView 用
Pine v5 スクリプト集です。Python でバックテスト → TradingView でリアルタイム
監視/発注、というパイプラインを完成させます。

## ファイル

| ファイル | 形態 | 用途 |
| --- | --- | --- |
| `elliott45_strategy.pine` | `strategy()` | TradingView の Strategy Tester でバックテスト。エントリ/SL/TP/partial+BE/2×ATR トレールが全部入りで動く |
| `elliott45_alerts.pine`   | `indicator()` | アラート/可視化専用。無料プランでも動く。Webhook 連携でブローカー自動発注が可能 |

## インポート手順

1. TradingView を開く
2. 下部メニューの **Pine Editor** を開く
3. 上記いずれかの `.pine` ファイルの中身をコピー＆ペースト
4. **Save → 名前を付けて保存** → **Add to chart**
5. 設定アイコンで **threshold_atr / 各 retrace 範囲 / risk per trade** を調整

## パラメータ一覧（Python 側と完全一致）

| Pine 入力名 | Python 引数 | 既定値 |
| --- | --- | --- |
| `threshold_atr` | `--threshold-atr` | `3.0` |
| `atr_period` | `--atr-period` | `14` |
| `wave2 retrace min/max` | `--r2-min/max` | `0.236 / 0.886` |
| `wave4 retrace min/max` | `--r4-min/max` | `0.118 / 0.618` |
| `require W3 > W1` | `WaveParams.require_w3_longer_than_w1` | `true` |
| `entry buffer (xW4)` | `--entry-buffer-frac` | `0.20` |
| `stop buffer (xW4)` | `--stop-buffer-frac` | `0.50` |
| `TP = pivot4 + (xW1)` | `--target-w1-mult` | `1.00` |
| `max pending bars` | `--max-pending-bars` | `24` |
| `max hold bars` | `--max-hold-bars` | `240` |
| `partial TP at +1R` | `--partial-tp-r 1.0` | `true` |
| `partial size` | `--partial-tp-size` | `0.50` |
| `move SL to BE on partial` | `--no-be-at-partial` (Python は反対フラグ) | `true` |
| `ATR Chandelier trailing stop` | `--trail-atr-mult 2.0` | `true` (mult=2.0) |
| `trail x ATR` | `--trail-atr-mult` | `2.0` |
| `risk per trade` | `--risk-per-trade` | `0.01` (= 1%) |
| `allow short setups` | `--no-short` (Python は反対フラグ) | `true` |

## Python ↔ Pine 等価項目

| 項目 | Python | Pine v5 |
| --- | --- | --- |
| ZigZag 反転確定 | extreme から ATR×thr 逆行で確定、`confirm_idx >= idx` | 同一 (`extKind` 状態機械) |
| 5 ピボット保持 | `pivots[i-4:i+1]` をローテーション | `array.shift/push` で 5 サイズ配列 |
| 5 波並び判定 | `('L','H','L','H','L')` / `('H','L','H','L','H')` | `P0k..P4k` の符号比較 |
| Wave1/2/3/4 ルール | R1/R2/R3 + S1/S2 | 同一 |
| エントリトリガー | `pivot4 ± entry_buffer_frac × W4` | 同一 |
| 初期 SL | `pivot4 ∓ stop_buffer_frac × W4` | 同一 |
| TP | `pivot4 ± target_w1_mult × W1` | 同一 |
| 待機期間 | `max_pending_bars` バーで失効 | 同一 (`pendBarsLeft`) |
| 部分利確 | +1R で `partial_tp_size` 分クローズ | 同一 (`strategy.exit` の `qty_percent`) |
| 建値移動 | `move_be_at_partial=True` で SL=entry | 同一 |
| ATR トレーリング | `high[1] − trail_atr_mult × ATR[1]` でしか上げない | 同一（同バー高値は使わない＝因果的） |
| 同バー SL+TP | SL 優先（保守） | TV 仕様: 同 bar `comment_loss` 優先 |
| 同バー partial+元SL | SL 優先（バグ修正済） | TV 仕様で限界あり ↓ |
| リスクサイズ | `equity × risk_per_trade / risk_per_unit` | 同一 (`sizeFromRisk`) |
| タイムアウト決済 | `max_hold_bars` 経過で `close[i]` | `strategy.close_all("timeout")` |

## Python と完全には一致しない点

TradingView の実行モデル上、以下の挙動は Python 実装と「ほぼ同じだが厳密には
異なる」ケースが出ます:

1. **同バー partial+元SL の優先順位**: Python は明示的に SL 優先で固定。Pine では
   `strategy.exit` 内部の order matching に依存。実データでは差は数%以内。
2. **TF outlier 除外**: Python は 1h 強制リサンプルで M1 混入を吸収。Pine は
   選択したチャート時間軸そのもので動くので、必ず **H1 チャート**に貼ってください。
3. **トレード約定価格**: Python は trigger 価格で確定。Pine は次バー始値かトリガー
   タッチ価格でフィル（broker-style fills は Strategy Tester 設定で再現可能）。
4. **複利オフ (fixed sizing)**: Python の `--fixed-sizing` 相当は Pine では
   `initial_capital` 一定 + `qty` を毎回手計算する作りなので、もとから複利オフ
   ベース。Strategy Tester の "Order size" を "% of equity" にすると複利 ON 相当。

## Webhook 連携（実弾運用）

`elliott45_alerts.pine` のアラート文字列はこの形式:

```
LONG OANDA:USDJPY 60  trig=146.234  sl=144.951  tp=148.722
```

ブローカー API (OANDA, Alpaca, MT5 bridge 等) に投げる用途には Webhook が便利:

1. TradingView 右上の **Alerts → Create Alert**
2. Condition: `Elliott Wave 4->5 Alerts → LONG (rich)` または `SHORT (rich)`
3. Webhook URL: 自分のサーバ
4. Message: 上記テンプレ + 必要に応じて JSON 加工

## 5 銘柄プリセット（Python 検証結果と整合）

`threshold_atr=3.0` 既定設定で全 9 銘柄一括検証済み（Python 側）:

| Symbol | win% | PF | DD | Sharpe |
| --- | ---: | ---: | ---: | ---: |
| USDJPY | 91.7% | 120 | -0.12% | +3.17 |
| EURJPY | 89.7% | 48 | -0.39% | +3.10 |
| GBPJPY | 87.4% | 50 | -0.28% | +3.15 |
| XAUUSD | 89.6% | 34 | -0.35% | +3.14 |
| NAS100 | 90.2% | 32 | -0.70% | +3.03 |

これらは **partial 1R+BE + 2×ATR trail + 固定サイズ + 取引コスト 0** での数値です。
TV 側 Strategy Tester で同じパラメータを設定すれば概ね一致するはず（誤差 ±5% 想定）。

## トラブルシューティング

| 症状 | 対処 |
| --- | --- |
| トレード数が Python と大きく違う | H1 チャート以外を使っていないか確認 / TradingView のバー履歴の長さ (有料プランで延びる) |
| シグナルが全く出ない | `threshold_atr` を `2.0` まで下げてみる / `r2/r4` の範囲を広げてみる |
| Strategy Tester で勝率が低い | 「Order size」「Commission」「Slippage」を設定し直す（Python の `--fixed-sizing` 相当に） |
| ライン/ラベルが表示されない | `Display` 系の入力を ON、または `Max bars back` を増やす |

## ライセンス

このスクリプトはリポジトリ全体と同じライセンスで配布しています。
