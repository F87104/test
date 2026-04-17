import { PageHeader } from "@/components/PageHeader";
import { ToolForm, type Field } from "@/components/ToolForm";

const fields: Field[] = [
  {
    name: "skills",
    label: "あなたのスキル / 経験 / 強み",
    type: "textarea",
    rows: 3,
    placeholder:
      "例: Webデザイン3年 / 元美容師 / Excel業務改善 / コーチング資格",
    required: true,
  },
  {
    name: "interests",
    label: "興味のある業界・分野",
    placeholder: "例: 美容・健康 / BtoB SaaS / 教育 / クリエイター支援",
  },
  {
    name: "hours",
    label: "確保できる作業時間(週あたり)",
    placeholder: "例: 平日2時間 + 土日6時間 = 約16時間/週",
    required: true,
  },
  {
    name: "budget",
    label: "初期に投下できる資金",
    placeholder: "例: 30万円まで / ほぼゼロ / 200万円OK",
    required: true,
  },
  {
    name: "currentIncome",
    label: "現在の月収(本業 / 副業)",
    placeholder: "例: 本業35万、副業0",
  },
  {
    name: "targetMonths",
    label: "月収100万円までの目標期間",
    type: "select",
    options: ["6ヶ月", "12ヶ月", "18ヶ月", "24ヶ月"],
  },
  {
    name: "constraints",
    label: "制約・絶対条件",
    type: "textarea",
    rows: 3,
    placeholder:
      "例: 地方在住 / 育児で日中は不可 / 顔出しNG / 在庫を持ちたくない",
  },
];

export default function Page() {
  return (
    <div>
      <PageHeader
        icon="🚀"
        title="月収100万円ロードマップ"
        description="あなたのスキル・時間・資金から、一人で月収100万円に届くビジネスモデル3案、単価×件数の数字設計、90日アクションプラン、撤退ラインまでAIが一括で提案します。"
      />
      <ToolForm
        tool="roadmap"
        fields={fields}
        submitLabel="ロードマップを作成する"
      />
    </div>
  );
}
