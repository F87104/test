import { PageHeader } from "@/components/PageHeader";
import { ToolForm, type Field } from "@/components/ToolForm";

const fields: Field[] = [
  {
    name: "skills",
    label: "あなたのスキル / 経験 / 強み",
    type: "textarea",
    rows: 3,
    placeholder:
      "例: ノーコード制作 / SEOライティング / Pythonスクリプト / 動画編集 / Notion運用",
    required: true,
  },
  {
    name: "interests",
    label: "関心領域・市場",
    placeholder: "例: 個人開発者向けツール / 副業者向け教材 / 旅行 / フィットネス",
  },
  {
    name: "hours",
    label: "立ち上げ期に確保できる作業時間(月)",
    placeholder: "例: 60時間/月(平日夜+土日)",
    required: true,
  },
  {
    name: "budget",
    label: "初期投資の上限",
    placeholder: "例: 10万円まで / ほぼゼロ / 100万円OK",
    required: true,
  },
  {
    name: "targetIncome",
    label: "目標とする月の純利益",
    type: "select",
    options: ["10万円", "30万円", "50万円", "100万円", "200万円以上"],
  },
  {
    name: "automationLevel",
    label: "自動化レベル(どこまで人手をなくしたいか)",
    type: "select",
    options: [
      "顧客対応・納品・課金まで完全自動",
      "サポートのみ自分で、それ以外は自動",
      "集客は自分で発信、納品〜課金は自動",
    ],
  },
  {
    name: "avoid",
    label: "絶対やりたくないこと",
    type: "textarea",
    rows: 3,
    placeholder:
      "例: 対面営業 / オンライン会議 / 在庫管理 / 顔出し / 電話対応",
  },
];

export default function Page() {
  return (
    <div>
      <PageHeader
        icon="🤖"
        title="無人ビジネス設計"
        description="商談・対面・1対1納品をゼロにし、決済から納品・サポート・集客まで自動で回るビジネスをAIが設計。具体的なツール名・自動化アーキテクチャ・撤退ラインまで提示します。"
      />
      <ToolForm
        tool="automated"
        fields={fields}
        submitLabel="無人ビジネス案を作る"
      />
    </div>
  );
}
