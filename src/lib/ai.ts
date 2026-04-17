import OpenAI from "openai";

let cached: OpenAI | null = null;

export function getClient(): OpenAI {
  if (cached) return cached;
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error(
      "OPENAI_API_KEY が設定されていません。`.env.local` に API キーを設定してください。"
    );
  }
  cached = new OpenAI({
    apiKey,
    baseURL: process.env.OPENAI_BASE_URL || undefined,
  });
  return cached;
}

export const DEFAULT_MODEL = process.env.OPENAI_MODEL || "gpt-4o-mini";

export type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

export async function chat(
  messages: ChatMessage[],
  opts: { temperature?: number; model?: string } = {}
): Promise<string> {
  const client = getClient();
  const completion = await client.chat.completions.create({
    model: opts.model || DEFAULT_MODEL,
    temperature: opts.temperature ?? 0.7,
    messages,
  });
  return completion.choices[0]?.message?.content?.trim() ?? "";
}
