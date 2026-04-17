import { PageHeader } from "@/components/PageHeader";
import { ToolForm, type Field } from "@/components/ToolForm";

const fields: Field[] = [
  {
    name: "serviceName",
    label: "サービス名",
    placeholder: "例: ひとり経理 LITE",
    required: true,
  },
  {
    name: "serviceDesc",
    label: "サービス概要",
    type: "textarea",
    rows: 3,
    placeholder: "何を、誰に、どんな形で提供するか。",
    required: true,
  },
  {
    name: "target",
    label: "ターゲット顧客と抱える課題",
    type: "textarea",
    rows: 3,
    placeholder: "例: 売上1,000万円以下のフリーランス。確定申告に毎年丸2日とられている。",
  },
  {
    name: "diff",
    label: "競合との差別化ポイント",
    type: "textarea",
    rows: 3,
    placeholder: "例: 完全オンライン / 領収書はスマホで撮るだけ / 月額固定制",
  },
  {
    name: "tone",
    label: "トーン",
    type: "select",
    options: [
      "信頼感がありつつ、わかりやすく",
      "情熱的・熱量高め",
      "落ち着いた高級感",
      "ポップ・親しみやすい",
    ],
  },
];

export default function Page() {
  return (
    <div>
      <PageHeader
        icon="🛍️"
        title="ランディング文案"
        description="LP・ECページ・サービス紹介ページのキャッチコピー、サブコピー、ベネフィット、CTA文言を一気に生成します。"
      />
      <ToolForm tool="landing" fields={fields} />
    </div>
  );
}
