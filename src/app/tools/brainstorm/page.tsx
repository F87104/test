import { PageHeader } from "@/components/PageHeader";
import { ToolForm, type Field } from "@/components/ToolForm";

const fields: Field[] = [
  {
    name: "theme",
    label: "テーマ / 課題",
    type: "textarea",
    rows: 3,
    placeholder:
      "例: 既存顧客のリピート率を上げる施策 / 新しいオンライン講座の企画",
    required: true,
  },
  {
    name: "constraints",
    label: "制約・前提",
    type: "textarea",
    rows: 3,
    placeholder: "例: 月の予算は5万円以内 / 1人で運営 / 平日夜のみ稼働",
  },
  {
    name: "audience",
    label: "ターゲット",
    placeholder: "例: 30代共働きの子育て世帯",
  },
];

export default function Page() {
  return (
    <div>
      <PageHeader
        icon="💡"
        title="アイデアブレスト"
        description="観点を変えながら一気に10案を提案。最後に有望なTop3もピックアップします。"
      />
      <ToolForm
        tool="brainstorm"
        fields={fields}
        submitLabel="10案出してもらう"
      />
    </div>
  );
}
