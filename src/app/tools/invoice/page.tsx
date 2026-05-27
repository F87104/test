import { PageHeader } from "@/components/PageHeader";
import { ToolForm, type Field } from "@/components/ToolForm";

const fields: Field[] = [
  {
    name: "docType",
    label: "書類種別",
    type: "select",
    options: ["請求書", "見積書", "納品書", "領収書"],
    required: true,
  },
  {
    name: "recipient",
    label: "宛先",
    placeholder: "例: 株式会社ABC 経理部 御中",
    required: true,
  },
  {
    name: "projectName",
    label: "案件名 / 内容",
    placeholder: "例: コーポレートサイト リニューアル 一式",
    required: true,
  },
  {
    name: "amount",
    label: "金額",
    placeholder: "例: ¥330,000(税込)",
    required: true,
  },
  {
    name: "dueDate",
    label: "支払期日 / 有効期限",
    placeholder: "例: 2026年5月31日(請求書発行日より30日以内)",
  },
  {
    name: "notes",
    label: "備考(振込先・分割条件・その他)",
    type: "textarea",
    rows: 4,
    placeholder: "例: 振込手数料はご負担ください。源泉徴収後の入金額は…",
  },
];

export default function Page() {
  return (
    <div>
      <PageHeader
        icon="🧾"
        title="請求書・見積書 送付メール"
        description="請求書や見積書を送るときに添える、丁寧で抜け漏れのないメール文面を生成します。"
      />
      <ToolForm tool="invoice" fields={fields} />
    </div>
  );
}
