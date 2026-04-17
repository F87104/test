export type Tool = {
  href: string;
  title: string;
  icon: string;
  summary: string;
  description: string;
  category:
    | "ひとり起業"
    | "営業・顧客"
    | "マーケティング"
    | "経理・事務"
    | "経営・企画";
};

export const tools: Tool[] = [
  {
    href: "/tools/roadmap",
    title: "月収100万円ロードマップ",
    icon: "🚀",
    summary:
      "あなたのスキル・時間・資金から、一人で月収100万円に届く道筋をAIが設計。",
    description:
      "ビジネスモデル3案、単価×件数の数字設計、90日アクションプラン、撤退ラインまで一括で提案します。",
    category: "ひとり起業",
  },
  {
    href: "/tools/automated",
    title: "無人ビジネス設計",
    icon: "🤖",
    summary:
      "商談・対面・1対1納品をなくし、人を介さず回るビジネスをAIが設計。",
    description:
      "デジタル商品・SaaS・広告メディア・自動配信などから3案を提案。決済/納品/サポート/集客の自動化スタックまで具体ツール名で提示します。",
    category: "ひとり起業",
  },
  {
    href: "/tools/email",
    title: "営業メール作成",
    icon: "✉️",
    summary: "新規開拓〜フォローまで、相手別に最適な営業メールを生成。",
    description:
      "宛先・目的・トーンを指定するだけで、件名と本文をワンクリックで作成します。",
    category: "営業・顧客",
  },
  {
    href: "/tools/reply",
    title: "顧客返信アシスタント",
    icon: "💬",
    summary: "クレーム・問い合わせ・見積依頼に、丁寧で角の立たない返信を作成。",
    description:
      "受信メールを貼り付けて、自社の立場と希望する対応方針を入力するだけ。",
    category: "営業・顧客",
  },
  {
    href: "/tools/invoice",
    title: "請求書・見積書文面",
    icon: "🧾",
    summary: "請求書・見積書に添える送付メールや備考欄の文面を生成。",
    description:
      "金額・支払期日・案件名から、丁寧で抜け漏れのない送付文面を作成します。",
    category: "経理・事務",
  },
  {
    href: "/tools/social",
    title: "SNS投稿ジェネレーター",
    icon: "📣",
    summary: "X / Instagram / LinkedIn 用に、商品・サービスの投稿文を量産。",
    description:
      "プラットフォーム、トーン、文字数を指定して複数案を一度に生成します。",
    category: "マーケティング",
  },
  {
    href: "/tools/landing",
    title: "ランディング文案",
    icon: "🛍️",
    summary: "サービス紹介、LPのキャッチコピー、ベネフィット文を生成。",
    description:
      "ターゲット・課題・差別化要素を入力して、刺さる訴求コピーを作成します。",
    category: "マーケティング",
  },
  {
    href: "/tools/meeting",
    title: "議事録・要約",
    icon: "📝",
    summary: "打ち合わせメモや文字起こしから、要約・ToDo・次アクションを抽出。",
    description:
      "長文を貼り付けるだけで、論点・決定事項・宿題を構造化してまとめます。",
    category: "経営・企画",
  },
  {
    href: "/tools/brainstorm",
    title: "アイデアブレスト",
    icon: "💡",
    summary: "新サービス・コンテンツ企画・キャンペーンのアイデアを発散。",
    description:
      "テーマと制約を入れると、観点を変えながら多面的にアイデアを提案します。",
    category: "経営・企画",
  },
  {
    href: "/tools/pricing",
    title: "料金プラン設計",
    icon: "💴",
    summary: "サービス内容から、3段階の料金プラン案と根拠を生成。",
    description:
      "ターゲットや原価感を入力すると、プラン名・価格・含まれる内容を提案。",
    category: "経営・企画",
  },
];

export const toolByHref = (href: string) => tools.find((t) => t.href === href);
