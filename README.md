# Solo Business AI — 一人で完結するビジネスAI

個人事業主・フリーランス・スモールビジネスのオーナーのための、**一人でビジネスを完結させるためのAIツールキット**です。

営業メールの作成、顧客への返信、請求書/見積書の送付メール、SNS投稿、LP の文案、議事録作成、アイデア出し、料金プラン設計まで、ひとりビジネスでよく発生する文章作業をすべて1つのアプリで賄えます。

## 含まれるツール

| カテゴリ | ツール | 用途 |
| --- | --- | --- |
| ひとり起業 | 🚀 月収100万円ロードマップ | スキル/時間/資金から到達ロードマップ・数字設計・90日プランを設計 |
| ひとり起業 | 🤖 無人ビジネス設計 | 商談・対面ゼロで回るビジネス案・自動化スタック・撤退ラインを設計 |
| 営業・顧客 | ✉️ 営業メール作成 | 新規開拓・商談打診のメールを生成 |
| 営業・顧客 | 💬 顧客返信アシスタント | クレーム / 問い合わせ / 見積依頼への返信 |
| 経理・事務 | 🧾 請求書・見積書 送付メール | 請求・見積の送付メール文面 |
| マーケティング | 📣 SNS投稿ジェネレーター | X / Instagram / LinkedIn 等向けの投稿を3案 |
| マーケティング | 🛍️ ランディング文案 | キャッチコピー / サブコピー / ベネフィット / CTA |
| 経営・企画 | 📝 議事録・要約 | メモや文字起こしから議事録・ToDo を抽出 |
| 経営・企画 | 💡 アイデアブレスト | テーマと制約から10案+おすすめTop3 |
| 経営・企画 | 💴 料金プラン設計 | 3段階の料金プラン+根拠+アップセル案 |

## セットアップ

### 必要環境

- Node.js 20.x 以上(推奨: 20 / 22)
- OpenAI API キー(または OpenAI 互換のエンドポイント / API キー)

### インストール

```bash
npm install
```

### 環境変数の設定

`.env.example` をコピーして `.env.local` を作成し、API キーを設定します。

```bash
cp .env.example .env.local
```

```dotenv
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 任意: モデルや別プロバイダーを切り替える場合
# OPENAI_MODEL=gpt-4o-mini
# OPENAI_BASE_URL=https://api.openai.com/v1
```

OpenAI 互換のプロバイダー(Together AI, Groq, OpenRouter, ローカル LLM など)も `OPENAI_BASE_URL` を変えるだけでそのまま利用できます。

### 開発サーバーの起動

```bash
npm run dev
```

ブラウザで [http://localhost:3000](http://localhost:3000) を開きます。

### 本番ビルド

```bash
npm run build
npm run start
```

## 使い方

1. 左サイドバーから利用したいツールを選びます。
2. フォームに必要事項を入力します(必須項目には `*` が付いています)。
3. 「**AIで生成する**」を押すと、右側のパネルに結果が表示されます。
4. 「**コピー**」ボタンでクリップボードへコピーし、メール / SNS / 資料へそのまま貼り付けてください。

## 技術スタック

- [Next.js 14](https://nextjs.org/) (App Router)
- TypeScript
- Tailwind CSS
- [openai](https://www.npmjs.com/package/openai) (OpenAI 互換クライアント)

## ディレクトリ構成

```
src/
  app/
    layout.tsx          # 共通レイアウト + サイドバー
    page.tsx            # ホーム(ツール一覧)
    globals.css
    api/generate/route.ts  # AI 生成エンドポイント
    tools/
      roadmap/page.tsx
      automated/page.tsx
      email/page.tsx
      reply/page.tsx
      invoice/page.tsx
      social/page.tsx
      landing/page.tsx
      meeting/page.tsx
      brainstorm/page.tsx
      pricing/page.tsx
  components/
    Sidebar.tsx
    PageHeader.tsx
    ToolForm.tsx        # 全ツール共通の入力フォーム
    ResultPanel.tsx     # 結果表示 + コピー
  lib/
    ai.ts               # OpenAI クライアント
    prompts.ts          # 各ツールのプロンプト
    tools.ts            # ツール定義(ナビゲーション/カード用)
```

## 新しいツールの追加方法

1. `src/lib/prompts.ts` の `ToolKey` と `buildMessages` に新しいキーを追加します。
2. `src/app/api/generate/route.ts` の `VALID_TOOLS` に新キーを追加します。
3. `src/lib/tools.ts` にツールのメタデータ(タイトル、アイコン、説明)を追加します。
4. `src/app/tools/<key>/page.tsx` を作り、`ToolForm` に渡すフィールドを定義します。

これだけで、サイドバー・ホーム一覧・ページ・API がそろいます。

## ライセンス

MIT
