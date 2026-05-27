# エリオット波動 研究フォルダ

このフォルダは、[F87104/sai](https://github.com/F87104/sai) リポジトリにアップロードされている下記 4 つの PDF（書名「FX 環境認識の定石」の関連章）に書かれている**エリオット波動の手法**を研究するための作業ディレクトリです。

## 一次資料（出典）

| 略称 | ファイル名 | 役割 |
| --- | --- | --- |
| ch1 | [`1章.pdf`](https://github.com/F87104/sai/blob/main/1%E7%AB%A0.pdf) | 環境認識の入門。各理論（ダウ／エリオット／通貨強弱／サイクル等）の位置づけ |
| dow | [`ダウ理論.pdf`](https://github.com/F87104/sai/blob/main/%E3%82%BF%E3%82%99%E3%82%A6%E7%90%86%E8%AB%96.pdf) | エリオット波動を学ぶ前提となるトレンド定義 |
| elliott | [`エリオット波動.pdf`](https://github.com/F87104/sai/blob/main/%E3%82%A8%E3%83%AA%E3%82%AA%E3%83%83%E3%83%88%E6%B3%A2%E5%8B%95.pdf) | 本体（Chapter 4・全 50 ページ）。基礎〜カウント〜トレード手順〜リアル例 |
| method | [`手法.pdf`](https://github.com/F87104/sai/blob/main/%E6%89%8B%E6%B3%95.pdf) | §55「フィボナッチを使った利益確定」§56「相場が大きく動いたときの正しい振る舞い」でエリオット波動と接続 |

> いずれも書籍 PDF を OCR（tesseract `jpn`）で抽出した結果に基づいてまとめています。OCR テキストは `raw_ocr/` 配下に保存しています。誤字や記号崩れがあるため、最終的な確認は元 PDF で行ってください。

## フォルダ構成

```
elliott_wave_research/
├── README.md                       … このファイル
├── 01_method/                      … 手法の体系的言語化（核ドキュメント）
│   └── METHOD.md
├── 02_rules_cheatsheet/            … 即参照したいルール／傾向のチートシート
│   └── RULES.md
├── 03_pattern_catalog/             … 推進波・調整波・イレギュラーのパターン辞典
│   └── PATTERNS.md
├── 04_counting_procedure/          … 一目均衡表「雲」を使った機械的カウント手順
│   └── COUNTING.md
├── 05_trade_playbook/              … 5波狙いの 4 ステップ・エントリー／決済テンプレ
│   └── PLAYBOOK.md
├── 06_real_trade_examples/         … 著者の GBP/AUD 実例＋自分の検証ログ用
│   └── EXAMPLE_GBPAUD_2023-07.md
├── 07_research_notes/              … 研究中の論点・疑問・追加調査メモ
│   └── OPEN_QUESTIONS.md
├── 08_backtest_ideas/              … この手法をバックテストするための仕様メモ
│   └── BACKTEST_SPEC.md
└── raw_ocr/                        … OCR で抽出した一次テキスト（PDF 4 冊分）
    ├── elliott_all.txt
    ├── ch1_all.txt
    ├── method_all.txt
    └── dow_all.txt
```

## 中核ドキュメント

まず読むべきは [`01_method/METHOD.md`](01_method/METHOD.md)。著者が「5 波狙い」と呼ぶ手法を一冊分まるごと体系化しています。
