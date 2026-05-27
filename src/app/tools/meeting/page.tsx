import { PageHeader } from "@/components/PageHeader";
import { ToolForm, type Field } from "@/components/ToolForm";

const fields: Field[] = [
  {
    name: "transcript",
    label: "打ち合わせメモ / 文字起こし",
    type: "textarea",
    rows: 14,
    placeholder:
      "Zoomの文字起こしや、打ち合わせ中に取ったメモをそのまま貼り付けてください。発言者名が無くてもOKです。",
    required: true,
  },
];

export default function Page() {
  return (
    <div>
      <PageHeader
        icon="📝"
        title="議事録・要約"
        description="長文のメモや文字起こしから、概要・論点・決定事項・ToDoを構造化して整理します。"
      />
      <ToolForm tool="meeting" fields={fields} submitLabel="議事録を作成する" />
    </div>
  );
}
