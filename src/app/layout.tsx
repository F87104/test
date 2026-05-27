import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Solo Business AI — 一人で完結するビジネスAI",
  description:
    "営業メール、請求書文面、SNS投稿、顧客対応、議事録、アイデア出しまで。個人事業主・フリーランスのための、一人で完結できるビジネスAIツールキット。",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja">
      <body className="bg-ink-50 text-ink-900 antialiased">
        <div className="min-h-screen flex">
          <Sidebar />
          <main className="flex-1 min-w-0">
            <div className="mx-auto max-w-5xl px-6 py-10">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
