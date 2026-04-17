import { NextRequest, NextResponse } from "next/server";
import { chat } from "@/lib/ai";
import { buildMessages, type ToolKey } from "@/lib/prompts";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const VALID_TOOLS: ToolKey[] = [
  "email",
  "reply",
  "invoice",
  "social",
  "landing",
  "meeting",
  "brainstorm",
  "pricing",
  "roadmap",
];

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as {
      tool?: string;
      input?: Record<string, string>;
      temperature?: number;
    };
    const tool = body.tool as ToolKey | undefined;
    if (!tool || !VALID_TOOLS.includes(tool)) {
      return NextResponse.json(
        { error: `不正なツール指定です: ${tool}` },
        { status: 400 }
      );
    }
    const input = body.input || {};
    const messages = buildMessages(tool, input);
    const text = await chat(messages, {
      temperature: typeof body.temperature === "number" ? body.temperature : 0.7,
    });
    return NextResponse.json({ text });
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "想定外のエラーが発生しました。";
    console.error("[/api/generate] error:", err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
