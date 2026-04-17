import type { ChatMessage } from "./ai";

const baseSystem =
  "あなたは日本の個人事業主・フリーランスを支援する優秀なビジネスアシスタントです。" +
  "回答は常に丁寧な日本語のビジネス文体で、過度な敬語の重複や冗長な前置きを避け、" +
  "実用的かつそのまま使える品質に仕上げてください。" +
  "Markdown を必要に応じて利用しますが、メール本文など指定があるものはプレーンテキストで返してください。";

export type ToolKey =
  | "email"
  | "reply"
  | "invoice"
  | "social"
  | "landing"
  | "meeting"
  | "brainstorm"
  | "pricing";

export function buildMessages(tool: ToolKey, input: Record<string, string>): ChatMessage[] {
  switch (tool) {
    case "email":
      return [
        { role: "system", content: baseSystem },
        {
          role: "user",
          content: `以下の条件で、日本語の営業メールを作成してください。

# 宛先・相手
${input.recipient || "未指定"}

# 目的
${input.purpose || "未指定"}

# 自分 / 自社の概要
${input.sender || "未指定"}

# トーン
${input.tone || "丁寧・誠実"}

# 補足
${input.notes || "特になし"}

# 出力フォーマット
件名: <ここに件名>

<ここに本文。署名は「[あなたの名前]」のようなプレースホルダで。>
`,
        },
      ];

    case "reply":
      return [
        { role: "system", content: baseSystem },
        {
          role: "user",
          content: `顧客からの以下のメッセージに対して、適切な返信メール本文を作成してください。

# 受信メッセージ
"""
${input.incoming || ""}
"""

# こちらの立場・状況
${input.context || "特になし"}

# 希望する対応方針
${input.policy || "丁寧に状況を説明し、誠実に対応する"}

# トーン
${input.tone || "丁寧・落ち着いた・誠実"}

# 出力フォーマット
件名: <ここに件名>

<本文。プレーンテキストで。署名は「[あなたの名前]」プレースホルダで。>`,
        },
      ];

    case "invoice":
      return [
        { role: "system", content: baseSystem },
        {
          role: "user",
          content: `請求書または見積書を送付するためのメール文面を作成してください。

# 種別
${input.docType || "請求書"}

# 案件名・内容
${input.projectName || "未指定"}

# 金額(税込/税抜の指定があれば含む)
${input.amount || "未指定"}

# 支払・有効期限
${input.dueDate || "未指定"}

# 備考(振込先・分割条件・その他連絡事項)
${input.notes || "特になし"}

# 宛先
${input.recipient || "未指定"}

# 出力フォーマット
件名: <ここに件名>

<本文(プレーンテキスト)。「請求書を添付の通りお送りします」のような形で、丁寧に。署名は[あなたの名前]プレースホルダ。>`,
        },
      ];

    case "social":
      return [
        { role: "system", content: baseSystem },
        {
          role: "user",
          content: `以下の条件でSNS投稿の案を **3案** 作成してください。

# プラットフォーム
${input.platform || "X (旧Twitter)"}

# 商品・サービス・テーマ
${input.topic || "未指定"}

# 訴求したいポイント
${input.benefits || "未指定"}

# ターゲット
${input.audience || "未指定"}

# トーン
${input.tone || "親しみやすく、信頼感のある"}

# 文字数の目安
${input.length || "プラットフォームに合わせて適切に"}

# 出力フォーマット
案1:
<本文>
ハッシュタグ: <#xxx #yyy>

案2:
...
案3:
...`,
        },
      ];

    case "landing":
      return [
        { role: "system", content: baseSystem },
        {
          role: "user",
          content: `ランディングページに使う訴求文(コピー)を作成してください。

# サービス名
${input.serviceName || "未指定"}

# サービス概要
${input.serviceDesc || "未指定"}

# ターゲット顧客と抱える課題
${input.target || "未指定"}

# 競合との差別化ポイント
${input.diff || "未指定"}

# 望むトーン
${input.tone || "信頼感がありつつ、わかりやすく"}

# 出力(以下の構成で Markdown)
## メインキャッチコピー(3案)
- 案1
- 案2
- 案3

## サブコピー(リード文)
<2〜3文>

## ベネフィット(箇条書き 3〜5)
- ...

## CTAボタン文言(3案)
- ...`,
        },
      ];

    case "meeting":
      return [
        { role: "system", content: baseSystem },
        {
          role: "user",
          content: `以下の打ち合わせメモ/文字起こしから、議事録としてまとめてください。

# 元テキスト
"""
${input.transcript || ""}
"""

# 出力フォーマット (Markdown)
## 概要
<3〜5行で要約>

## 主要な論点
- ...

## 決定事項
- ...

## ToDo / 次アクション
- [ ] 担当: <名前または[未定]> / 期限: <YYYY-MM-DD or [未定]> / 内容: ...

## 気になる点・リスク
- ...`,
        },
      ];

    case "brainstorm":
      return [
        { role: "system", content: baseSystem },
        {
          role: "user",
          content: `以下のテーマでアイデアを **10案** 出してください。観点を変え、安全策と挑戦的な案の両方を含めてください。

# テーマ / 課題
${input.theme || "未指定"}

# 制約・前提
${input.constraints || "特になし"}

# ターゲット
${input.audience || "未指定"}

# 出力フォーマット (Markdown)
1. **<アイデア名>** — 一言説明
   - 想定ターゲット:
   - 期待効果:
   - 実行のヒント:

2. ...
(全10案)

最後に「## 個人的おすすめ Top3」として、特に有望な3案を理由付きで挙げてください。`,
        },
      ];

    case "pricing":
      return [
        { role: "system", content: baseSystem },
        {
          role: "user",
          content: `以下のサービスについて、3段階の料金プラン(ライト / スタンダード / プロ 等)を提案してください。

# サービス内容
${input.serviceDesc || "未指定"}

# ターゲット顧客
${input.target || "未指定"}

# 原価・工数感(あれば)
${input.cost || "未指定"}

# 競合・相場(あれば)
${input.market || "未指定"}

# 出力フォーマット (Markdown)
## プラン比較表
| プラン | 想定ターゲット | 価格(税込) | 含まれる内容 | 制約 |
|---|---|---|---|---|
| <名前> | ... | ¥XX,XXX | ... | ... |
| <名前> | ... | ¥XX,XXX | ... | ... |
| <名前> | ... | ¥XX,XXX | ... | ... |

## 価格設定の根拠
- ...

## アップセル/オプション案
- ...`,
        },
      ];
  }
}
