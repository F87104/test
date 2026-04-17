import Link from "next/link";
import { tools } from "@/lib/tools";

export default function HomePage() {
  const categories = Array.from(new Set(tools.map((t) => t.category)));

  return (
    <div>
      <section className="mb-10">
        <span className="badge bg-brand-50 text-brand-700 border border-brand-100">
          一人で完結するビジネスAI
        </span>
        <h1 className="mt-4 text-3xl md:text-4xl font-bold tracking-tight text-ink-950 leading-tight">
          営業も、経理も、マーケも。
          <br className="hidden md:inline" />
          ひとりビジネスの仕事を、AIで丸ごと巻き取る。
        </h1>
        <p className="mt-4 text-ink-600 leading-relaxed max-w-2xl">
          個人事業主・フリーランス・スモールビジネスのオーナーのための、一人で完結するAIツールキットです。
          メール、見積、SNS、議事録、企画、料金設計まで、左メニューから必要なツールを選んで今すぐ使えます。
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/tools/email" className="btn-primary">
            まずは営業メールを作ってみる
          </Link>
          <Link href="/tools/brainstorm" className="btn-secondary">
            アイデアを出す
          </Link>
        </div>
      </section>

      {categories.map((cat) => (
        <section key={cat} className="mb-10">
          <h2 className="text-sm font-semibold text-ink-500 uppercase tracking-wider mb-3">
            {cat}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {tools
              .filter((t) => t.category === cat)
              .map((t) => (
                <Link
                  key={t.href}
                  href={t.href}
                  className="card p-5 hover:shadow-lg hover:border-brand-200 transition group"
                >
                  <div className="flex items-start gap-3">
                    <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-xl shrink-0">
                      {t.icon}
                    </span>
                    <div className="min-w-0">
                      <div className="font-semibold text-ink-900 group-hover:text-brand-800">
                        {t.title}
                      </div>
                      <p className="mt-1 text-sm text-ink-600 leading-relaxed">
                        {t.summary}
                      </p>
                    </div>
                  </div>
                </Link>
              ))}
          </div>
        </section>
      ))}

      <section className="mt-12 card p-6 bg-gradient-to-br from-brand-50 to-white border-brand-100">
        <h3 className="font-semibold text-ink-900">使い方はかんたん 3 STEP</h3>
        <ol className="mt-3 grid gap-3 sm:grid-cols-3 text-sm text-ink-700">
          <li className="flex gap-3">
            <span className="badge bg-white border border-brand-200 text-brand-700">
              1
            </span>
            <span>左メニューから使いたいツールを選ぶ</span>
          </li>
          <li className="flex gap-3">
            <span className="badge bg-white border border-brand-200 text-brand-700">
              2
            </span>
            <span>条件を入力して「AIで生成する」をクリック</span>
          </li>
          <li className="flex gap-3">
            <span className="badge bg-white border border-brand-200 text-brand-700">
              3
            </span>
            <span>結果をコピーして、メール / SNS / 資料へ貼り付け</span>
          </li>
        </ol>
      </section>
    </div>
  );
}
