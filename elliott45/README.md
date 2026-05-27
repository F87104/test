# Elliott Wave 4 → 5 Backtester

このリポジトリに同梱されている H1 (1 時間足) の CSV 過去データを使い、
**エリオット波動の第4波 → 第5波狙い**戦略を Python で検証します。

* データ: リポジトリ直下と各 `*2014-2024/` フォルダにある MT4/MT5 形式 CSV
  （`<TICKER>,<DTYYYYMMDD>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>`）。
* 対象銘柄: `USDJPY, EURJPY, AUDJPY, CHFJPY, GBPJPY, XAUUSD, XAGUSD, NAS100, SPX500`。
* 時間軸: H1 にリサンプリングして統一（GBPJPY の古いファイルが M1 で
  保存されていた件は loader が自動補正）。

## セットアップ

```bash
pip install -r elliott45/requirements.txt
```

## 使い方

```bash
# 全銘柄一括 (デフォルト・複利あり)
python -m elliott45.main --all

# 固定サイズ（複利なし、毎トレード starting_equity × risk% で建玉）
python -m elliott45.main --all --fixed-sizing

# 単一銘柄
python -m elliott45.main --symbol USDJPY --threshold-atr 3.0

# トレードログ・サマリを保存
python -m elliott45.main --all --fixed-sizing \
    --summary-out elliott45/results/summary.json \
    --trades-out  elliott45/results/trades.csv
```

主な CLI オプション:

| オプション | 既定値 | 説明 |
| --- | --- | --- |
| `--threshold-atr` | `3.0` | ZigZag 反転確定に必要な ATR 倍率（大きいほどピボットが少なく＝大きな波） |
| `--atr-period` | `14` | ATR 期間 |
| `--r2-min` / `--r2-max` | `0.236 / 0.886` | 第2波の第1波に対する戻り率の許容範囲 |
| `--r4-min` / `--r4-max` | `0.118 / 0.618` | 第4波の第3波に対する戻り率の許容範囲 |
| `--target-w1-mult` | `1.0` | 第5波の利確距離 = W1 長 × この倍率（pivot4 から測る） |
| `--stop-buffer-frac` | `0.50` | SL を pivot4 から W4 長 × この値だけ外に置く |
| `--entry-buffer-frac` | `0.20` | エントリーは pivot4 から W4 長 × この値だけ進んだ価格に到達したらフィル |
| `--risk-per-trade` | `0.01` | 1 トレード当たりリスク（口座資金の比率） |
| `--max-pending-bars` | `24` | シグナル発生後にエントリーを待つ最大バー数 |
| `--max-hold-bars` | `240` | エントリー後にポジションを保持する最大バー数（タイムアウト決済） |
| `--no-short` | — | ショート方向の同型シグナルを無視 |
| `--fixed-sizing` | — | 複利を切る（毎回 `starting_equity * risk_per_trade` で建玉） |

## アルゴリズム

### 1. ピボット検出（`src/zigzag.py`）

価格バーを 1 本ずつ走査し、現在の極値（高値 or 安値）から
`threshold_atr × ATR(atr_period)` だけ反対方向に動いたら、その極値を
ピボットとして確定。**ピボットは過去の極値の bar index と、確定した
未来側の bar index (`confirm_idx`) を分けて保持** しているので、戦略は
`confirm_idx` 以降のみで動作し未来情報を見ません。

### 2. エリオット 1〜4 波の検出（`src/elliott.py`）

直近 5 個のピボット `p0,p1,p2,p3,p4` を `L-H-L-H-L`（ロング）
または `H-L-H-L-H`（ショート）の並びで検査し、次の **厳格ルール** を
すべて満たすときに「Wave-4 終了 / Wave-5 狙い」のセットアップを生成
します:

* **R1**: 第2波は第1波の起点を割らない。
* **R2**: 第4波は第1波の価格帯に侵入しない。
* **R3**: 第3波は第1波より長い（既知の波で「3 が最短ではない」を最低限担保）。
* **S1**: 第2波の第1波に対する戻りが `[r2_min, r2_max]` の範囲。
* **S2**: 第4波の第3波に対する戻りが `[r4_min, r4_max]` の範囲。

ロング側の SL/TP/トリガーは

```
trigger = p4 + entry_buffer_frac × W4
stop    = p4 − stop_buffer_frac  × W4
target  = p4 + target_w1_mult    × W1     # = pivot4 + 100% × Wave1 長
```

ショート側はその鏡像。

### 3. バックテスト（`src/backtest.py`）

* セットアップは `p4.confirm_idx + 1` バー目から `max_pending_bars` の
  間、トリガー価格にタッチしたら**そのバーのトリガー価格**で約定。
* SL/TP は約定後インバーで判定し、同バーで両方ヒット時は SL 優先（保守側）。
* `max_hold_bars` 経過したらクローズ価格で強制決済。
* ポジションは常時 1 枚。複利の有無は `--fixed-sizing` で切替。
* 手数料・スリッページ・スワップは未モデル化。

## 検証結果（GitHub 同梱データ・固定サイズ・risk=1%）

`threshold_atr=3.0` の既定設定、`--fixed-sizing`（複利なし）、1 トレード
あたり口座 1% リスクで全 9 銘柄を走らせた結果:

| Symbol | bars | 期間(年) | trades | win% | PF | E[R] | Total ret | Max DD | Sharpe |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| USDJPY | 75,960 | 12.4 | 217 | 62.7% | 2.74 | +0.63R | +137.3% | -2.8% | +1.65 |
| EURJPY | 75,174 | 12.4 | 214 | 65.4% | 3.05 | +0.71R | +152.1% | -4.4% | +1.81 |
| AUDJPY | 73,953 | 12.4 | 160 | 68.8% | 3.85 | +0.87R | +139.6% | -3.0% | +1.81 |
| CHFJPY | 76,982 | 12.4 | 159 | 61.6% | 2.98 | +0.76R | +120.6% | -3.7% | +1.52 |
| GBPJPY | 81,199 | 13.4 | 235 | 62.6% | 2.90 | +0.71R | +166.3% | -3.3% | +1.67 |
| XAUUSD | 70,410 | 12.4 | 220 | 62.7% | 2.73 | +0.64R | +141.6% | -3.6% | +1.69 |
| XAGUSD | 70,218 | 12.4 | 179 | 63.7% | 2.74 | +0.62R | +110.7% | -4.8% | +1.49 |
| NAS100 | 67,391 | 11.5 | 205 | 66.8% | 3.48 | +0.82R | +168.8% | -2.4% | +2.02 |
| SPX500 | 67,862 | 11.5 | 183 | 57.9% | 2.48 | +0.62R | +113.7% | -3.8% | +1.42 |

**ポートフォリオ平均**: 勝率 約 63%、PF 約 2.9、期待値 +0.71R、最大 DD ≈ -3.6%。

### 閾値感度（`threshold_atr` を 2.0/3.0/4.0/5.0 で振った範囲）

* 勝率: **55 〜 71%**
* PF: **2.0 〜 4.6**
* 期待値: **+0.40 〜 +1.03R**
* DD: **-1.9 〜 -5.4%**

→ いずれの設定でも全銘柄プラス。**極端な過剰最適化ではなく、ルール自体が
H1 のトレンド転換初動を捉えていることを示唆**します。

## 既知の前提・制約（生データに対する読み方の注意）

* **未モデル化コスト**: スプレッド/手数料/スワップ/スリッページを含めて
  いないため、ライブの PF はこれより 0.3〜0.8 ほど低く出る可能性があります。
* **同バー SL+TP は SL 優先**（保守側）。それでも上記成績が出ています。
* **データ品質**: 配布 CSV の `GBPJPY` 2013〜2024 年は実際には M1 で
  保存されていたため、loader が一律 H1 へ再サンプリングしています。
* **エリオットの一義性**: 同じ価格列でも閾値次第で見える波が違うため、
  `threshold_atr` を変えながら同じシグナルが出る銘柄ほど信頼度が高いと
  解釈してください。

## ディレクトリ構成

```
elliott45/
├── README.md
├── requirements.txt
├── main.py                 # CLI ランナー
├── src/
│   ├── data_loader.py      # CSV 一括ロード + H1 リサンプル
│   ├── zigzag.py           # 因果的 ATR ZigZag
│   ├── elliott.py          # Wave-4→5 セットアップ生成
│   ├── backtest.py         # イベント駆動バックテスト
│   └── metrics.py          # 勝率 / PF / 期待値 / DD / Sharpe
├── tests/
│   ├── test_zigzag.py
│   └── test_elliott.py
└── results/                # サマリ JSON / トレード CSV 出力先
```
