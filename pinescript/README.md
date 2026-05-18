# TradingView Pine Script v5 移植版

Python の検証ツールと**完全に同じロジック**で動く Pine Script を提供します。
これにより TradingView 上でエントリー・決済位置を視覚化し、リアルタイムでアラートを受け取れます。

---

## 2 つのスクリプト

| ファイル | 用途 | TradingView での実体 |
| --- | --- | --- |
| `trend_break_strategy.pine` | **戦略バックテスター版**。SL/TP まで自動で描画、TradingView の Strategy Tester で集計可能 | `strategy()` |
| `trend_break_alerts.pine` | **インジケーター版**。シグナルマーカー + SL/TP 補助線 + サイズング助言テーブル + アラート | `indicator()` |

両者は**同一のシグナル生成ロジック**。違いは「TV 内で約定するか」「アラート専用か」だけ。

---

## インポート手順 (TradingView)

1. TradingView で対象の通貨ペア / 時間足を開く（例：`OANDA:XAUUSD` の `1H`）
2. 画面下の **「Pine エディタ」** タブを開く
3. **「+ 新規」→「空のスクリプト」** を選択
4. このフォルダの `.pine` ファイルの内容をコピペ
5. **「保存」**（適当な名前）→ **「チャートに追加」**
6. 設定アイコンを開き、**プリセット** を選択（XAUUSD / XAGUSD / GBPJPY / USDJPY / EURJPY / カスタム）

---

## 推奨プリセット一覧

`configs/best_*.json` から自動転記。プリセットを選ぶと該当パラメータが自動適用されます。

| 通貨 | level_kind | lookback_3m | exclude_3m | SL ATR× | TP RR | session | margin | バックテスト総リターン |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **XAUUSD** | mid | 480 | 120 | 2.0 | 3.0 | 全 | 0.0 | **+99.1% / 11.5年** |
| **XAGUSD** | mid | 360 | 180 | 2.0 | 3.0 | Asia+NY | 0.0 | +61.3% |
| **GBPJPY** | mid | 360 | 180 | 2.5 | 3.0 | Asia+NY | 0.0 | +56.9% |
| **USDJPY** | mid | 480 | 180 | 2.0 | 3.0 | Asia+NY | 0.0 | +43.2% |
| **EURJPY** | mid | 360 | 60 | 2.5 | 3.0 | 全 | 0.5 ATR | +16.1% |

---

## Strategy 版の使い方

### 1. チャート上でエントリー位置を視覚的に確認

スクリプトをチャートに追加すると、自動的に：

- 🟢 **緑の▲** = LONG エントリー位置
- 🔴 **赤の▼** = SHORT エントリー位置
- **緑の水平線** = TP (利確水準)
- **赤の水平線** = SL (損切り水準)
- **背景色** = シグナル発火バー

### 2. Strategy Tester で Python 結果と照合

画面下の **「Strategy Tester」** タブで以下が見られます：

- Net Profit / Profit Factor / Win Rate / Max Drawdown
- トレード一覧（エントリー価格・SL・TP・損益）
- Equity Curve

Python 側 (`results/_winners_*/SYMBOL_*/`) と数値が **±数%以内で一致** すれば移植成功です。

> 注: TradingView の Strategy Tester は ATR の計算精度や fill 価格の扱いで若干の差が出ます。
> Python 側の Backtest を「真の基準」、Pine 側は「視覚化と取引判断補助」と位置付けてください。

---

## Alerts 版の使い方（**リアルタイム運用の本命**）

### 1. チャートに追加 + プリセット選択

`trend_break_alerts.pine` を Strategy 版と同じ手順でインポート → 通貨ペアに合わせたプリセットを選択。

### 2. アラート作成

シグナルが出るたびに通知が来るように：

1. チャート上で右クリック → **「アラートを追加」**（または `Alt+A`）
2. 「条件」プルダウンで **`TrendBreakAlert`** を選択
3. 「条件」サブプルダウンで以下から選択：
   - **🟢 LONG signal (rich)** … SL/TP/サイズ込みの詳細メッセージ
   - **🔴 SHORT signal (rich)** … 同上
   - **🟢 LONG signal (simple)** … `XAUUSD LONG @ 2348.12` のみ
   - **🔴 SHORT signal (simple)** … 同上
4. 「アクション」で **メール / アプリ / PUSH / Webhook URL** を選択
5. **「作成」** をクリック

### 3. 受信例（rich 版）

```
🟢 LONG  OANDA:XAUUSD @ 2348.12  SL=2335.86  TP=2384.90
        size=8.16  RR=1:3.00  ATR=6.13  2025-07-08T14:00:00Z
```

これを見て、ご自身の MT4/MT5/ブローカー UI で **そのまま発注** できます。

### 4. Webhook で完全自動化（上級）

「アクション」で Webhook URL を指定すると、メッセージが JSON として送信されます。
ご自身のサーバで受け取り、ブローカー API に流せば **完全自動化** も可能です。
（ただし TradingView 有料プラン Pro 以上が必要）

---

## Python ↔ Pine の同等性

両者は以下を **完全に一致** させています：

| 項目 | Python | Pine v5 |
| --- | --- | --- |
| 中期高値ライン | `high.shift(1).rolling(lookback_3m).max()` | `ta.highest(high[1], lookback_3m)` |
| 中期安値ライン | `low.shift(1).rolling(lookback_3m).min()` | `ta.lowest (low[1],  lookback_3m)` |
| 直近接触除外 | `shift(1).rolling(exclude).max() < highLevel` | `ta.highest(high[1], exclude) < highLevel` |
| シグナル条件 | `(close > highLevel) AND (no recent touch)` | 同上 |
| SL 計算 | `entry − sl_atr_mult × ATR(14)` | `entry − use_sl_atr × ta.atr(14)` |
| TP 計算 | `entry + tp_rr × |entry − SL|` | 同上 |
| ポジションサイズ | `equity × risk% / |entry − SL|` | 同上 |
| 約定タイミング | `entry_fill="next_open"` | Pine デフォルト (シグナル次バー始値) |
| 同バー SL/TP hit | SL 優先（保守的） | Pine デフォルト (同じ挙動) |

### 想定される差異

| 差異要因 | 影響 |
| --- | --- |
| TradingView の `ta.atr` は Wilder 法、Python も Wilder → ほぼ一致 | ±0.1% |
| TV ブローカー側データと Python 側 CSV の出処差 | ±1-3% |
| TV Strategy Tester の手数料/スリッページ既定 = 0 | Python と同条件 |
| `process_orders_on_close=false` (デフォルト) → 次バー始値約定 | 完全一致 |

→ 期待される一致度: **トレード数 ±3%, 総リターン ±5%以内**

---

## チャートで Python の結果を「重ね合わせる」方法

Python が出した過去のトレードを TradingView で見たい場合：

### 方法 A: Strategy 版で再走（推奨）

`trend_break_strategy.pine` を該当通貨に貼り、対応するプリセットを選ぶ → 自動でエントリー・決済マーカーが出ます。

### 方法 B: trades.csv をマニュアルでマーキング

Python が出した `trades.csv` を TradingView の **「描画ツール → 矢印」** で 1 つずつプロットする。
本格的に重ねたい場合は専用の Pine スクリプトを作って `array` に座標を埋め込む方法もありますが、過去 100 件超のトレードを Pine 内にハードコードするのは非推奨。

### 方法 C: 直近の発火だけ可視化

`trend_break_alerts.pine` を貼ると、最新のシグナルバーの SL/TP 補助線が描画されます（30 バー先まで）。
過去のトレード集計は Python 側 `chart_price.png` を見るのが最速。

---

## トラブルシューティング

### Q. シグナルが全然出ない
- プリセットがチャートのシンボルと一致しているか確認（XAUUSD のプリセットを EURUSD に当てると発火しない）
- 時間足が H1（1時間）になっているか確認（H4/D1 だと lookback の意味が変わる）
- ヒストリーが十分か（少なくとも `lookback_3m + 100` 本必要）

### Q. Strategy Tester の数値が Python と大きく違う
- 通貨ペア / シンボルを TV と Python 側で完全に同じソースから取っているか
- TV 側で時間足 / セッション時間 / 取引時間を H1 UTC に揃えているか
- 設定ダイアログの「Properties」タブで `Slippage=0`、`Commission=0`、`Initial Capital=10000` になっているか

### Q. シグナルバーで pending entry が消えてしまう
- 次のバーが出る前にチャートタイムフレームを切り替えると `var pending_dir` がリセットされます
- 一度シグナルが出たら新しい H1 バーが完成するまで触らない

### Q. アラート文に固有値が入らない（`{{close}}` のまま）
- 「アラートを追加」で「条件」を **このスクリプトの alertcondition** から選んでいるか
- カスタム文を独自に書くと変数は展開されません

---

## 次のステップ

このフォルダの 2 ファイルをそのまま使えば、**「Python で検証 → Pine で視覚化 → 実運用」** の流れが完成します。
さらに高度な使い方：

- 複数通貨で別々のアラートを設定 → スマホに 5 通貨分の push 通知が来る
- Webhook + 自作サーバ → 完全自動化（自己責任）
- Strategy 版を H4 / D1 にも適用 → スイング版を別個に研究

質問があれば Python 側 README + `docs/design_document.md` も併せてご覧ください。
