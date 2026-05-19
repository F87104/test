"""メルマガ本文から「自分ごと化ワーク」を生成する.

2 つのモードを用意:
- ``template``: 外部 API なしで動く. 件名と本文から固定の問いを組み立てる.
- ``llm``: OpenAI 互換 API を呼んで, ケース要約 + 4〜5 個の状況依存の問いを生成.

Slack には「ケース要約」「ワーク（問いリスト）」「24時間以内に試せる一歩」を
ひとまとまりで投稿する. interval ごとの復習通知では, 視点を変えた別の問い
（行動編 / 経過編 / 習慣化編 / 振り返り編）を出して, 同じネタを多面的に咀嚼させる.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Protocol


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# データモデル
# --------------------------------------------------------------------------- #


@dataclass
class Worksheet:
    """1 通のメルマガに対応する学習ワーク."""

    case_summary: str
    questions: List[str] = field(default_factory=list)
    action_prompt: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "Worksheet":
        data = json.loads(raw)
        return cls(
            case_summary=data.get("case_summary", ""),
            questions=list(data.get("questions") or []),
            action_prompt=data.get("action_prompt", ""),
        )


# --------------------------------------------------------------------------- #
# 生成器
# --------------------------------------------------------------------------- #


class WorksheetGenerator(Protocol):
    def generate(self, *, subject: str, body: str) -> Worksheet: ...


def _trim(text: str, max_chars: int) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text or "").strip()
    return text if len(text) <= max_chars else text[:max_chars] + "…"


# --------- (1) テンプレ版: 外部依存なし, いつでも動く ----------------------- #


_TEMPLATE_QUESTIONS: List[str] = [
    "今日のメルマガを「3行」で要約してください。一行目は事実、二行目は主張、三行目は自分への問いです。",
    "ここで提示された **核心の主張** は何だと思いますか？ 賛成・反対・保留のどれを選び、その根拠を一つ挙げてください。",
    "もし自分が同じ状況・テーマに直面したら、**どう考え、どう行動しますか？** 過去の似た経験を一つ思い出して書き出してみましょう。",
    "**24時間以内** に試せる「最小の一歩」を 1 つだけ決めてください。やる/やらないが明確になる粒度で（例: 朝6時に起きる、本を10ページ読む）。",
]


class TemplateWorksheetGenerator:
    """API キーなしでも常に動く, 固定テンプレベースの生成器."""

    def __init__(self, questions: Optional[List[str]] = None):
        self._questions = list(questions) if questions else list(_TEMPLATE_QUESTIONS)

    def generate(self, *, subject: str, body: str) -> Worksheet:
        case = self._build_case(subject=subject, body=body)
        return Worksheet(
            case_summary=case,
            questions=list(self._questions),
            action_prompt=(
                "答えはこのスレッドに **箇条書きで** 返信してください。"
                "1日 / 3日 / 7日 / 30日後に角度を変えた振り返り通知が届きます。"
            ),
        )

    @staticmethod
    def _build_case(*, subject: str, body: str) -> str:
        head = _trim(body, 280)
        if not head:
            return f"今日のテーマ: *{subject}*"
        return (
            f"今日のテーマ: *{subject}*\n"
            f"\n> {head}".replace("\n", "\n> ", head.count("\n"))
        )


# --------- (2) LLM 版: OpenAI 互換 API でケース別の問いを生成 -------------- #


_LLM_SYSTEM_PROMPT = """あなたは勝間和代さんのメルマガを使った学習コーチです。
読者が **メルマガ本文を「自分ごと化」できるワーク** を日本語で設計してください。
出力は必ず以下の JSON スキーマに従い、余計な前置きやコードブロックを付けないでください。

{
  "case_summary": "本文を 2〜3 行で要約し、最後に『あなたならどう考え、どう行動しますか？』のフックを添える",
  "questions": [
    "事実理解を問う問い（What）",
    "主張への賛否と根拠を問う問い（Why / Counter）",
    "読者自身の状況に置き換える問い（Self-application: 『もしあなたが…なら』）",
    "24時間以内の最小の一歩を決めさせる問い（Action）"
  ],
  "action_prompt": "ワークの取り組み方を 1〜2 文で促すメッセージ"
}

ルール:
- 質問は最大 5 個、最低 3 個。
- 必ず *日本語* で。
- 「もしあなたが◯◯なら、どう考えどう行動しますか？」型の問いを 1 つ以上含める。
- 抽象論にならず、生活・仕事の具体的シーンを想起させる文言にする。"""


class LLMWorksheetGenerator:
    """OpenAI 互換 chat API でケース別ワークを生成する."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 30,
        session=None,
    ):
        if not api_key:
            raise ValueError("LLMWorksheetGenerator requires an api_key")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        if session is None:
            import requests

            session = requests.Session()
        self.session = session

    def generate(self, *, subject: str, body: str) -> Worksheet:
        body_trimmed = _trim(body, 1800)
        user_msg = (
            f"以下はメルマガの件名と本文です。これに対するワークを設計してください。\n\n"
            f"# 件名\n{subject}\n\n"
            f"# 本文\n{body_trimmed}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.4,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
        }
        try:
            resp = self.session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return Worksheet(
                case_summary=str(parsed.get("case_summary") or "").strip(),
                questions=[str(q).strip() for q in (parsed.get("questions") or []) if str(q).strip()],
                action_prompt=str(parsed.get("action_prompt") or "").strip(),
            )
        except Exception as exc:
            logger.warning("LLM ワーク生成に失敗, テンプレにフォールバック: %s", exc)
            return TemplateWorksheetGenerator().generate(subject=subject, body=body)


# --------- ファクトリ --------------------------------------------------------- #


def build_generator(
    *,
    mode: str = "template",
    openai_api_key: Optional[str] = None,
    openai_model: str = "gpt-4o-mini",
    openai_base_url: str = "https://api.openai.com/v1",
) -> WorksheetGenerator:
    """``WORKSHEET_MODE`` の値で生成器を切り替える. 'off' は無効化用."""
    mode = (mode or "template").strip().lower()
    if mode == "off":
        return _NoopGenerator()
    if mode == "llm":
        if not openai_api_key:
            logger.warning("WORKSHEET_MODE=llm だが OPENAI_API_KEY が無いためテンプレに切替")
            return TemplateWorksheetGenerator()
        return LLMWorksheetGenerator(
            api_key=openai_api_key,
            model=openai_model,
            base_url=openai_base_url,
        )
    return TemplateWorksheetGenerator()


class _NoopGenerator:
    def generate(self, *, subject: str, body: str) -> Worksheet:
        return Worksheet(case_summary="", questions=[], action_prompt="")


# --------------------------------------------------------------------------- #
# interval ごとの復習問い
# --------------------------------------------------------------------------- #


@dataclass
class ReviewPrompt:
    label: str
    questions: List[str]


_REVIEW_PROMPTS = {
    1: ReviewPrompt(
        label="行動編（1日後）",
        questions=[
            "昨日のワークで決めた「最小の一歩」は実行できましたか？ 結果を一言で。",
            "やってみて気付いた *小さな違和感や発見* は何ですか？",
            "今日もう一回続けるとしたら、何を変えますか？",
        ],
    ),
    3: ReviewPrompt(
        label="経過編（3日後）",
        questions=[
            "3日経って、最初の答えと今の答えに *差分* はありますか？",
            "周囲の人や生活の中で、関連する出来事を思い出せましたか？",
            "ワークで挙げた行動は続いていますか？ 続かなかった理由を一行で。",
        ],
    ),
    7: ReviewPrompt(
        label="習慣化編（1週間後）",
        questions=[
            "1週間経った今、この学びは *習慣* になっていますか？ なっていないなら障害は何？",
            "他の知識・経験と *線でつながった* 部分はありますか？",
            "次の1週間、続けるか・捨てるか・変形するか、どれを選びますか？",
        ],
    ),
    30: ReviewPrompt(
        label="振り返り編（1ヶ月後）",
        questions=[
            "1ヶ月前のあなたと今のあなた、何が変わりましたか？ 数字や事実で書けるとベスト。",
            "あの日のメルマガを *いま読み返したら* 何が新しく見えてきますか？",
            "他者にこのテーマを 1 分で説明するなら、どう話しますか？",
        ],
    ),
}


def review_prompt_for(interval_days: int) -> ReviewPrompt:
    """指定 interval にもっとも近い既定プロンプトを返す（無ければ近似）."""
    if interval_days in _REVIEW_PROMPTS:
        return _REVIEW_PROMPTS[interval_days]
    closest = min(_REVIEW_PROMPTS.keys(), key=lambda d: abs(d - interval_days))
    base = _REVIEW_PROMPTS[closest]
    return ReviewPrompt(
        label=f"振り返り（{interval_days}日後）",
        questions=list(base.questions),
    )
