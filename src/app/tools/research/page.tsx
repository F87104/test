import { PageHeader } from "@/components/PageHeader";
import { ToolForm, type Field } from "@/components/ToolForm";

const fields: Field[] = [
  {
    name: "theme",
    label: "リサーチテーマ / 知りたいこと",
    type: "textarea",
    rows: 3,
    placeholder:
      "例: 海外で流行っているが日本にまだ来ていないフィンテックサービス / シニア向けデジタルヘルスケアの最新動向",
    required: true,
  },
  {
    name: "markets",
    label: "対象市場・国",
    placeholder: "例: 米国・英国・ドイツ・フランス・北欧 を中心に",
  },
  {
    name: "period",
    label: "対象期間",
    placeholder: "例: 直近12ヶ月(2025〜2026年を優先)",
  },
  {
    name: "depth",
    label: "リサーチの深さ",
    type: "select",
    options: [
      "クイック(5〜8トピックを表形式で)",
      "標準(8〜12カテゴリ、ソース15件以上)",
      "深掘り(20カテゴリ以上、各トピックに数字・競合・規制まで)",
    ],
  },
  {
    name: "outputFormat",
    label: "出力フォーマットの希望",
    placeholder: "例: Markdown + 表形式 + 引用URL / スプレッドシートに貼れるTSV",
  },
  {
    name: "audience",
    label: "想定読者(誰がそのリサーチ結果を使うか)",
    placeholder: "例: ひとり起業家 / 中堅企業の新規事業担当者 / 投資家",
  },
  {
    name: "goal",
    label: "ゴール(リサーチ結果で何を判断したいか)",
    type: "textarea",
    rows: 2,
    placeholder:
      "例: 自分が参入すべきトピックを3つに絞りたい / 競合がいない穴を見つけたい",
  },
  {
    name: "exclude",
    label: "除外したい論点・触れて欲しくないテーマ",
    type: "textarea",
    rows: 2,
    placeholder: "例: 暗号資産 / ギャンブル系 / 法的にグレーなもの",
  },
  {
    name: "targetAI",
    label: "投げる先のAI(任意)",
    type: "select",
    options: [
      "Perplexity (Deep Research)",
      "ChatGPT (Search / Deep Research)",
      "Claude (Web Search)",
      "Gemini (Deep Research)",
      "未定 / 複数のAIで使いたい",
    ],
  },
];

export default function Page() {
  return (
    <div>
      <PageHeader
        icon="🔍"
        title="リサーチ・プロンプト生成"
        description="他のAI(Perplexity / ChatGPT / Claude / Gemini)に投げて高品質な調査結果を得るための、完成形プロンプトを自動生成します。英語/日本語の検索クエリ・引用ルール・出力フォーマット・フォローアップ質問まで一括で組み立てます。"
      />
      <ToolForm
        tool="research"
        fields={fields}
        submitLabel="プロンプトを生成する"
      />
    </div>
  );
}
