"use client";

import { useState } from "react";

export function ResultPanel({
  text,
  loading,
}: {
  text: string;
  loading: boolean;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (!text) return;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="card p-5 sticky top-6">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-ink-800">生成結果</div>
        <button
          type="button"
          className="btn-secondary !py-1.5 !px-3 text-xs"
          onClick={copy}
          disabled={!text}
        >
          {copied ? "コピーしました" : "コピー"}
        </button>
      </div>

      {loading && !text ? (
        <div className="space-y-2 animate-pulse">
          <div className="h-3 bg-ink-100 rounded w-3/4" />
          <div className="h-3 bg-ink-100 rounded w-5/6" />
          <div className="h-3 bg-ink-100 rounded w-2/3" />
          <div className="h-3 bg-ink-100 rounded w-4/5" />
          <div className="h-3 bg-ink-100 rounded w-1/2" />
        </div>
      ) : text ? (
        <pre className="whitespace-pre-wrap break-words text-sm leading-relaxed text-ink-800 font-sans max-h-[70vh] overflow-y-auto">
          {text}
        </pre>
      ) : (
        <div className="text-sm text-ink-500 leading-relaxed">
          フォームに必要事項を入力して「AIで生成する」を押すと、ここに結果が表示されます。
          <br />
          コピーしてそのままメールやSNSへ貼り付けて使えます。
        </div>
      )}
    </div>
  );
}
