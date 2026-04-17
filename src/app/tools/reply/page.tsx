import { PageHeader } from "@/components/PageHeader";
import { ToolForm, type Field } from "@/components/ToolForm";

const fields: Field[] = [
  {
    name: "incoming",
    label: "受信したメッセージ",
    type: "textarea",
    rows: 8,
    placeholder: "顧客から届いたメール本文をそのまま貼り付けてください。",
    required: true,
  },
  {
    name: "context",
    label: "こちらの状況・背景",
    type: "textarea",
    rows: 3,
    placeholder:
      "例: 納期遅延の原因はこちらにある / 在庫切れだが代替商品を提案できる",
  },
  {
    name: "policy",
    label: "希望する対応方針",
    type: "textarea",
    rows: 3,
    placeholder: "例: お詫びを述べた上で、新しい納期を提案。割引クーポンも案内。",
    required: true,
  },
  {
    name: "tone",
    label: "トーン",
    type: "select",
    options: [
      "丁寧・落ち着いた・誠実",
      "親しみやすい(常連顧客向け)",
      "毅然と・冷静",
      "謝罪を強めに",
    ],
  },
];

export default function Page() {
  return (
    <div>
      <PageHeader
        icon="💬"
        title="顧客返信アシスタント"
        description="クレームや問い合わせに、感情を逆なでせず誠実に返答する文面を生成します。"
      />
      <ToolForm tool="reply" fields={fields} />
    </div>
  );
}
