import { PageHeader } from "@/components/PageHeader";
import { ToolForm, type Field } from "@/components/ToolForm";

const fields: Field[] = [
  {
    name: "serviceDesc",
    label: "サービス内容",
    type: "textarea",
    rows: 4,
    placeholder: "提供するサービスの具体的な内容、納品物、所要時間など。",
    required: true,
  },
  {
    name: "target",
    label: "ターゲット顧客",
    placeholder: "例: 売上1〜3億円規模のEC事業者",
    required: true,
  },
  {
    name: "cost",
    label: "原価・工数感(任意)",
    type: "textarea",
    rows: 2,
    placeholder: "例: 1案件につき作業時間10時間。外注費は1万円程度。",
  },
  {
    name: "market",
    label: "競合・相場(任意)",
    type: "textarea",
    rows: 2,
    placeholder: "例: 競合は月額3〜5万円。納期は2週間が一般的。",
  },
];

export default function Page() {
  return (
    <div>
      <PageHeader
        icon="💴"
        title="料金プラン設計"
        description="3段階の料金プラン(松竹梅)を、含まれる内容と価格設定の根拠つきで提案します。"
      />
      <ToolForm tool="pricing" fields={fields} submitLabel="料金プランを作る" />
    </div>
  );
}
