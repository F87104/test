# Python バックテスター

Pine 戦略 `elliott_5wave_saido.pine` と**同じロジック**を Python で実装し、リポジトリ既存の CSV データで素早く検証するためのツール。

## ファイル

| ファイル | 役割 |
| --- | --- |
| `elliott_5wave_backtest.py` | バックテストのコア（単一 CSV / フォルダスキャン両対応） |
| `run_full_scan.py` | リポジトリ内の各通貨 H1 を集計し、複数バリアントを比較するラッパ |
| `results/scan_summary.csv` | バリアント × 通貨の集計結果 |
| `results/REPORT.md` | 結果の解釈と推奨セットアップ |

## 必要環境

- Python 3.9+（標準ライブラリのみ。pandas/numpy 不要）

## 使い方

### 単一 CSV を回す

```bash
python3 elliott_5wave_backtest.py "../../USDJPY_H1_2025.csv"
```

### リポジトリ全通貨を一括検証

```bash
# リポジトリルートで実行
python3 elliott_wave_research/10_python_backtest/run_full_scan.py \
    --variant default \
    --out elliott_wave_research/10_python_backtest/results/scan_summary.csv
```

### よく使うバリアント

```bash
# 推奨: HTF フィルタ off / Fib on / トレール
python3 run_full_scan.py --variant best_no_htf --no-htf

# 検出数最大 (HTF・Fib 両方 off)
python3 run_full_scan.py --variant maximum --no-htf --no-fib

# Long 専用
python3 run_full_scan.py --variant long_only --direction Long

# 通貨を絞る
python3 run_full_scan.py --variant test --symbols USDJPY_H1,XAUUSD_H1
```

## 出力の見方

```
[USDJPY_H1] bars= 75964 | trades= 107 | win= 52.3% | PF= 3.62 | ret= +18.49% | DD=  -1.77% | E[trade]=+172.85
```

- `bars`: 入力バー数
- `trades`: 確定トレード数
- `win`: 勝率
- `PF`: プロフィットファクター (gross win / gross loss)
- `ret`: 累積リターン %（初期資金比）
- `DD`: 最大ドローダウン %
- `E[trade]`: 1 トレードあたり期待値（金額）

## Pine との一致度

- ロウソク足の OHLC, 一目均衡表の雲, ATR, EMA, 状態機械, 推進波 3 ルール, Fib 検算, SL/TP, トレール, 雲反転撤退 — すべて同一仕様。
- 違い: Pine は `request.security` で正しい上位足を取得しますが、Python は同一 CSV を `aggregate(factor=4)` で簡易集約しています。厳密な MTF 検証は Pine 側でクロスチェック推奨。

## トレード履歴を出力する

```bash
python3 elliott_5wave_backtest.py "../../USDJPY_H1_2025.csv" \
    --trades-out results/trades_usdjpy_2025.csv
```

CSV カラム: `file, dir, entry_time, entry_price, exit_time, exit_price, sl, tp, reason, pnl`
