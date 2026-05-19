from unittest.mock import MagicMock

import pytest

from katsuma_to_slack.worksheet import (
    LLMWorksheetGenerator,
    TemplateWorksheetGenerator,
    Worksheet,
    build_generator,
    review_prompt_for,
)


def test_template_generator_returns_questions_and_case():
    gen = TemplateWorksheetGenerator()
    ws = gen.generate(
        subject="勝間和代の毎日メルマガ #100 - 習慣の力",
        body="今日のテーマは『習慣の力』。\n小さな一歩を毎日続けることが…",
    )
    assert ws.case_summary
    assert "習慣の力" in ws.case_summary or "習慣" in ws.case_summary
    assert len(ws.questions) >= 3
    joined = " ".join(ws.questions)
    assert "もし自分が同じ状況" in joined
    assert ws.action_prompt


def test_template_generator_handles_empty_body():
    gen = TemplateWorksheetGenerator()
    ws = gen.generate(subject="件名のみ", body="")
    assert "件名のみ" in ws.case_summary
    assert ws.questions


def test_worksheet_round_trip_json():
    ws = Worksheet(
        case_summary="ケース",
        questions=["Q1", "Q2"],
        action_prompt="やってみよう",
    )
    raw = ws.to_json()
    restored = Worksheet.from_json(raw)
    assert restored == ws


def test_review_prompt_for_known_intervals():
    p1 = review_prompt_for(1)
    p7 = review_prompt_for(7)
    assert "行動" in p1.label
    assert "習慣化" in p7.label
    assert len(p1.questions) >= 3
    assert len(p7.questions) >= 3


def test_review_prompt_for_unknown_interval_falls_back_close():
    p = review_prompt_for(2)
    assert "2日後" in p.label
    assert p.questions


def test_build_generator_modes():
    assert isinstance(build_generator(mode="template"), TemplateWorksheetGenerator)
    fallback = build_generator(mode="llm")
    assert isinstance(fallback, TemplateWorksheetGenerator)
    off = build_generator(mode="off")
    out = off.generate(subject="x", body="y")
    assert out.questions == []


def test_llm_generator_parses_json_response():
    session = MagicMock()
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"case_summary":"今日は習慣の話","questions":'
                        '["Q1","もしあなたが同じ立場なら？","Q3","今日の一歩は？"],'
                        '"action_prompt":"スレッドに返信してね"}'
                    )
                }
            }
        ]
    }
    session.post.return_value = response

    gen = LLMWorksheetGenerator(api_key="sk-test", session=session)
    ws = gen.generate(subject="件名", body="本文" * 10)

    assert ws.case_summary == "今日は習慣の話"
    assert len(ws.questions) == 4
    assert ws.action_prompt == "スレッドに返信してね"
    sent = session.post.call_args.kwargs["json"]
    assert sent["model"] == "gpt-4o-mini"
    assert sent["response_format"] == {"type": "json_object"}


def test_llm_generator_falls_back_on_error():
    session = MagicMock()
    session.post.side_effect = RuntimeError("boom")
    gen = LLMWorksheetGenerator(api_key="sk-test", session=session)
    ws = gen.generate(subject="件名X", body="本文")
    assert ws.questions
    assert "件名X" in ws.case_summary


def test_llm_generator_requires_key():
    with pytest.raises(ValueError):
        LLMWorksheetGenerator(api_key="")
