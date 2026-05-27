import { PageHeader } from "@/components/PageHeader";
import { ToolForm, type Field } from "@/components/ToolForm";

const fields: Field[] = [
  {
    name: "recipient",
    label: "宛先(相手の会社・名前・役職など)",
    placeholder: "例: 株式会社ABC マーケティング部 田中様",
    required: true,
  },
  {
    name: "purpose",
    label: "メールの目的",
    type: "textarea",
    rows: 3,
    placeholder:
      "例: 自社のSNS運用代行サービスを紹介し、30分のオンライン打ち合わせを依頼したい",
    required: true,
  },
  {
    name: "sender",
    label: "自分(自社)について",
    type: "textarea",
    rows: 3,
    placeholder:
      "例: 山田太郎。フリーランスのSNSマーケター。中小企業10社以上の運用実績あり。",
  },
  {
    name: "tone",
    label: "トーン",
    type: "select",
    options: [
      "丁寧・誠実(初回向け)",
      "カジュアル・フレンドリー",
      "簡潔・要点のみ",
      "熱意を伝える",
    ],
  },
  {
    name: "notes",
    label: "補足(必ず入れたい情報・避けたい表現など)",
    type: "textarea",
    rows: 3,
    placeholder: "例: 過去にお会いしたことを冒頭で触れる / 価格には触れない",
  },
];

export default function Page() {
  return (
    <div>
      <PageHeader
        icon="✉️"
        title="営業メール作成"
        description="宛先・目的・トーンを入れるだけで、すぐ送れる品質の営業メールを生成します。"
      />
      <ToolForm tool="email" fields={fields} />
    </div>
  );
}
