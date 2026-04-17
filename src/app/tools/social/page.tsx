import { PageHeader } from "@/components/PageHeader";
import { ToolForm, type Field } from "@/components/ToolForm";

const fields: Field[] = [
  {
    name: "platform",
    label: "プラットフォーム",
    type: "select",
    options: [
      "X (旧Twitter)",
      "Instagram",
      "LinkedIn",
      "Facebook",
      "Threads",
      "note",
    ],
    required: true,
  },
  {
    name: "topic",
    label: "テーマ / 商品 / サービス",
    placeholder: "例: 個人事業主向けのオンライン経理代行サービス",
    required: true,
  },
  {
    name: "benefits",
    label: "訴求したいポイント",
    type: "textarea",
    rows: 3,
    placeholder: "例: 月5,000円から / 領収書は写真送るだけ / 確定申告まで丸投げOK",
  },
  {
    name: "audience",
    label: "ターゲット",
    placeholder: "例: 開業3年以内の30〜40代フリーランス",
  },
  {
    name: "tone",
    label: "トーン",
    type: "select",
    options: [
      "親しみやすく、信頼感のある",
      "プロフェッショナル",
      "ユーモア・くだけた",
      "共感ベース(悩みに寄り添う)",
    ],
  },
  {
    name: "length",
    label: "文字数の目安",
    placeholder: "例: 140字 / 300字 / 500字",
  },
];

export default function Page() {
  return (
    <div>
      <PageHeader
        icon="📣"
        title="SNS投稿ジェネレーター"
        description="プラットフォームに合わせた投稿文を一度に3案生成。気に入った案をそのままコピーできます。"
      />
      <ToolForm tool="social" fields={fields} />
    </div>
  );
}
