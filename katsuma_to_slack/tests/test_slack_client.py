from unittest.mock import MagicMock

from katsuma_to_slack.slack_client import (
    SlackPoster,
    build_mailmagazine_blocks,
    build_reminder_blocks,
)


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


def test_reminder_blocks_link_to_permalink():
    blocks = build_reminder_blocks(
        subject="勝間和代の毎日メルマガ #100",
        interval_days=7,
        permalink="https://slack.example/p1",
    )
    rendered = str(blocks)
    assert "7日後の復習" in rendered
    assert "https://slack.example/p1" in rendered

    blocks2 = build_reminder_blocks(
        subject="勝間和代の毎日メルマガ #100",
        interval_days=7,
        permalink=None,
    )
    rendered2 = str(blocks2)
    assert "7日後の復習" in rendered2
