"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { tools } from "@/lib/tools";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-72 shrink-0 border-r border-ink-100 bg-white min-h-screen sticky top-0 hidden md:flex md:flex-col">
      <div className="px-6 py-6 border-b border-ink-100">
        <Link href="/" className="flex items-center gap-2.5 group">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white text-lg font-bold shadow-soft">
            S
          </span>
          <div className="leading-tight">
            <div className="font-semibold text-ink-900">Solo Business AI</div>
            <div className="text-xs text-ink-500">一人で完結するAIツール</div>
          </div>
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <div className="px-3 mb-2 text-xs font-semibold text-ink-500 uppercase tracking-wider">
          ツール
        </div>
        <ul className="space-y-0.5">
          {tools.map((t) => {
            const active = pathname === t.href;
            return (
              <li key={t.href}>
                <Link
                  href={t.href}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                    active
                      ? "bg-brand-50 text-brand-800 font-medium"
                      : "text-ink-700 hover:bg-ink-50"
                  }`}
                >
                  <span className="text-lg leading-none w-5 text-center" aria-hidden>
                    {t.icon}
                  </span>
                  <span className="truncate">{t.title}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="px-4 py-4 border-t border-ink-100 text-xs text-ink-500 leading-relaxed">
        <div className="font-medium text-ink-700 mb-1">個人事業主・フリーランス向け</div>
        営業から経理、マーケまで。
        ひとりビジネスを丸ごとAIが支援します。
      </div>
    </aside>
  );
}
