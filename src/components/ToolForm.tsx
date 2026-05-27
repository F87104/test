"use client";

import { useState } from "react";
import type { ToolKey } from "@/lib/prompts";
import { ResultPanel } from "./ResultPanel";

export type Field = {
  name: string;
  label: string;
  placeholder?: string;
  type?: "input" | "textarea" | "select";
  options?: string[];
  required?: boolean;
  hint?: string;
  rows?: number;
};

export function ToolForm({
  tool,
  fields,
  submitLabel = "AIで生成する",
  initial = {},
}: {
  tool: ToolKey;
  fields: Field[];
  submitLabel?: string;
  initial?: Record<string, string>;
}) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const v: Record<string, string> = { ...initial };
    for (const f of fields) if (!(f.name in v)) v[f.name] = "";
    return v;
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string>("");
  const [error, setError] = useState<string>("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setResult("");
    setLoading(true);
    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ tool, input: values }),
      });
      const data = (await res.json()) as { text?: string; error?: string };
      if (!res.ok) {
        throw new Error(data.error || `エラー (${res.status})`);
      }
      setResult(data.text || "");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "エラーが発生しました。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <form onSubmit={onSubmit} className="lg:col-span-3 card p-6 space-y-5">
        {fields.map((f) => (
          <div key={f.name}>
            <label className="label" htmlFor={f.name}>
              {f.label}
              {f.required && <span className="text-brand-600 ml-1">*</span>}
            </label>
            {f.type === "textarea" ? (
              <textarea
                id={f.name}
                className="textarea"
                rows={f.rows ?? 4}
                placeholder={f.placeholder}
                value={values[f.name] || ""}
                required={f.required}
                onChange={(e) =>
                  setValues((v) => ({ ...v, [f.name]: e.target.value }))
                }
              />
            ) : f.type === "select" ? (
              <select
                id={f.name}
                className="select"
                value={values[f.name] || ""}
                required={f.required}
                onChange={(e) =>
                  setValues((v) => ({ ...v, [f.name]: e.target.value }))
                }
              >
                <option value="">選択してください</option>
                {(f.options || []).map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id={f.name}
                className="input"
                placeholder={f.placeholder}
                value={values[f.name] || ""}
                required={f.required}
                onChange={(e) =>
                  setValues((v) => ({ ...v, [f.name]: e.target.value }))
                }
              />
            )}
            {f.hint && (
              <p className="mt-1 text-xs text-ink-500">{f.hint}</p>
            )}
          </div>
        ))}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800">
            {error}
          </div>
        )}

        <div className="flex items-center gap-3 pt-1">
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? (
              <>
                <Spinner /> 生成中...
              </>
            ) : (
              submitLabel
            )}
          </button>
          <button
            type="button"
            className="btn-ghost"
            onClick={() => {
              const cleared: Record<string, string> = {};
              for (const f of fields) cleared[f.name] = "";
              setValues(cleared);
              setResult("");
              setError("");
            }}
            disabled={loading}
          >
            クリア
          </button>
        </div>
      </form>

      <div className="lg:col-span-2">
        <ResultPanel text={result} loading={loading} />
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <svg
      className="animate-spin h-4 w-4"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}
