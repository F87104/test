from unittest.mock import MagicMock

from katsuma_to_slack.slack_client import (
    SlackPoster,
    build_mailmagazine_blocks,
    build_reminder_blocks,
    build_worksheet_blocks,
)
from katsuma_to_slack.worksheet import Worksheet, review_prompt_for


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_data=None, text: str = "ok"):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


def test_webhook_post_sends_payload():
    session = MagicMock()
    session.post.return_value = _FakeResponse(200)
    poster = SlackPoster(webhook_url="https://hooks.example/x", session=session)

    res = poster.post_message(text="hi", blocks=[{"type": "section"}])

    assert res.ok
    assert session.post.call_args.args[0] == "https://hooks.example/x"
    sent = session.post.call_args.kwargs["json"]
    assert sent["text"] == "hi"
    assert sent["blocks"] == [{"type": "section"}]


def test_api_post_returns_ts_and_permalink():
    session = MagicMock()
    session.post.return_value = _FakeResponse(200, {"ok": True, "ts": "111.222"})
    session.get.return_value = _FakeResponse(
        200, {"ok": True, "permalink": "https://slack.example/p1"}
    )
    poster = SlackPoster(
        bot_token="xoxb-test",
        channel_id="C123",
        session=session,
    )

    res = poster.post_message(text="hi", blocks=[{"type": "section"}], thread_ts="0.0")

    assert res.ok
    assert res.ts == "111.222"
    assert res.permalink == "https://slack.example/p1"
    body = session.post.call_args.kwargs["json"]
    assert body["channel"] == "C123"
    assert body["thread_ts"] == "0.0"


def test_api_post_propagates_error():
    session = MagicMock()
    session.post.return_value = _FakeResponse(200, {"ok": False, "error": "channel_not_found"})
    poster = SlackPoster(bot_token="xoxb-test", channel_id="C123", session=session)

    res = poster.post_message(text="hi")
    assert not res.ok
    assert res.error == "channel_not_found"


def test_supports_threading_only_with_bot_token():
    p_webhook = SlackPoster(webhook_url="https://hooks.example/x")
    p_bot = SlackPoster(bot_token="xoxb", channel_id="C1")
    assert p_webhook.supports_threading is False
    assert p_bot.supports_threading is True


def test_blocks_render_subject_and_summary():
    blocks = build_mailmagazine_blocks(
        subject="勝間和代の毎日メルマガ #100",
        sender="info@kazuyokatsuma.com",
        received_at_str="2026-05-19 06:00 JST",
        summary="本日は『習慣の力』について。",
    )
    rendered = str(blocks)
    assert "勝間和代の毎日メルマガ #100" in rendered
    assert "本日は『習慣の力』について。" in rendered


def test_worksheet_blocks_render_questions():
    ws = Worksheet(
        case_summary="今日のテーマ: *習慣の力*",
        questions=[
            "今日のメルマガを3行で要約してください。",
            "もし自分が同じ状況なら、どう考え、どう行動しますか？",
            "24時間以内に試せる一歩は？",
        ],
        action_prompt="スレッドに返信してください。",
    )
    blocks = build_worksheet_blocks(worksheet=ws)
    rendered = str(blocks)
    assert "今日のワーク" in rendered
    assert "Q1." in rendered and "Q2." in rendered and "Q3." in rendered
    assert "もし自分が同じ状況" in rendered
    assert "スレッドに返信" in rendered


def test_reminder_blocks_include_review_prompt_and_original_questions():
    review = review_prompt_for(1)
    blocks = build_reminder_blocks(
        subject="勝間和代の毎日メルマガ #100",
        interval_days=1,
        permalink="https://slack.example/p1",
        review=review,
        original_questions=[
            "今日のメルマガを3行で要約してください。",
            "もし自分が同じ状況なら、どう考え、どう行動しますか？",
        ],
    )
    rendered = str(blocks)
    assert "行動編" in rendered
    assert "https://slack.example/p1" in rendered
    assert "あの日のワーク" in rendered
    assert "もし自分が同じ状況" in rendered


def test_reminder_blocks_work_without_permalink_or_review():
    blocks = build_reminder_blocks(
        subject="勝間和代の毎日メルマガ #100",
        interval_days=7,
        permalink=None,
        review=None,
        original_questions=None,
    )
    rendered = str(blocks)
    assert "7日後の復習" in rendered
    assert "勝間和代の毎日メルマガ #100" in rendered
