# Pine v6 Strategy: Elliott 5-Wave Targeting (Saido reproduction)

## ファイル

- [`elliott_5wave_saido.pine`](elliott_5wave_saido.pine) — TradingView Pine v6 戦略本体

## 使い方

1. TradingView でチャートを開く（推奨: H1 のメジャー通貨ペア、または XAUUSD）
2. Pine エディタで `elliott_5wave_saido.pine` の中身を貼り付けて「チャートに追加」
3. Strategy Tester タブで結果を確認

## デフォルト推奨設定（バックテスト検証済み）

| 項目 | 推奨値 | 理由 |
| --- | --- | --- |
| Direction | Both | 多くのペアで両方向有効 |
| Higher-TF filter | **OFF** | 検証で逆効果のことが多かった |
| Fib retrace filter | ON (38.2–90 / 20–70) | 緩めに保つ |
| Elliott strict rules | 全て ON | 安全性のため |
| SL placement | Wave2 | 著者の標準 |
| SL buffer ATR | 0.2 | ヒゲ突き刺し対策 |
| TP mode | **Trail_ATR** | Fib 単独は機能しない |
| Trail ATR mult | 2.0 | ATR×2 が安定 |
| Cloud-flip exit | ON | 著者が言う「雲を割ったら手仕舞い」を再現 |
| Max bars in trade | 200 | 保有しすぎ防止 |

## 機能対応表（書籍 ↔ Pine）

| 書籍の記述 | Pine 上の実装 |
| --- | --- |
| 一目均衡表「雲」でカウント | `f_senkouA`, `f_senkouB`, `cloudTop`, `cloudBot` |
| 雲を下抜けた波→1波（短売り）／上抜けた波→1波（長買い） | `crossUp`/`crossDown` から状態 0→1 へ遷移 |
| 2波は1波始点を割らない | `i_rule_w2_no_break` |
| 4波は1波終点を割らない | `i_rule_w4_no_break` |
| 3波は最短にならない | `i_rule_w3_not_shortest` |
| 2波 戻し 61.8–78.6%, 4波 戻し 38.2–50% | Fib filter 入力 (`i_w2_min_pct`〜`i_w4_max_pct`) |
| 中期足 4波完成 ＋ 短期足 3波初動でエントリー | wave-5 確認バー = "短期足 3波初動" の代理として entry |
| 長期足トレンド・勢いの確認 | `i_use_ltf_filter` + `i_ltf_kind` |
| 損切り = 2波の終点 (または 1波始点) | `i_sl_mode` |
| 利確 = Fib 61.8% / 161.8% またはトレール | `i_tp_mode` |
| 5波中に雲を割ったら手仕舞い | `i_cloud_flip_exit` |
| 通貨強弱 | （未実装）別インジケータと併用してください |

## 100% 再現できなかった部分

書籍の以下の要素は本質的に裁量で、Pine では数値パラメータに置換しています。

- 「フラッグの角度」「ヒゲの飛び出しの許容範囲」 → `i_sl_buffer_atr`、Fib min/max
- 「カウントの微修正」 → 状態機械を 1 度しか走らせない（ミスカウントは次の機会まで待つ）
- 「相場の勢いがあるかどうかの感覚」 → HTF EMA slope filter / Cloud filter（OFF 推奨）
- 「通貨強弱」 → 別途インジケータが必要（次の課題）
- 「実トレードでカウントを途中で修正」 → 自動戦略では非対応

## バックテスト結果

`../10_python_backtest/results/REPORT.md` を参照。同じロジックを Python で 9 通貨 × 11 バリアントで検証してあります。

## 既知の制限

- `request.security` で取得する HTF データは `lookahead_off` を指定しており、将来情報を使わないように設定済み。
- バー確定（`barstate.isconfirmed`）でのみ状態遷移する設計のため、リアルタイム描画は確定後に反映されます（リペイント防止）。
- TradingView の Strategy Tester はデフォルトで `process_orders_on_close = true`、複利 OFF、コミッション 0.2% でセット。実運用前にスプレッド/スワップを実環境に合わせて調整してください。
