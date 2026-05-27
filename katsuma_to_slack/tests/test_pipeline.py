from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

from katsuma_to_slack.config import Config
from katsuma_to_slack.gmail_client import FetchedEmail
from katsuma_to_slack.pipeline import (
    ingest_new_mailmagazines,
    send_due_reminders,
)
from katsuma_to_slack.slack_client import SlackPostResult
from katsuma_to_slack.store import Store
from katsuma_to_slack.worksheet import TemplateWorksheetGenerator, Worksheet


def _cfg(tmp_path: Path) -> Config:
    return Config(
        gmail_address="me@example.com",
        gmail_app_password="x",
        slack_webhook_url="https://hooks.example/x",
        slack_bot_token="xoxb-test",
        slack_channel_id="C123",
        review_intervals_days=[1, 3, 7, 30],
        db_path=str(tmp_path / "db.sqlite3"),
        katsuma_from="info@kazuyokatsuma.com",
        katsuma_subject_contains="勝間",
        worksheet_mode="template",
    )


def _mail(subject: str = "勝間和代の毎日メルマガ #100", mid: str = "<a@example.com>") -> FetchedEmail:
    return FetchedEmail(
        message_id=mid,
        subject=subject,
        sender="勝間和代 <info@kazuyokatsuma.com>",
        received_at=datetime(2026, 5, 19, 6, 0, tzinfo=timezone.utc),
        body_text="本日のテーマは『習慣の力』。\n小さな一歩を毎日続けることが…",
    )


def test_ingest_skips_already_seen(tmp_path: Path):
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path_resolved)

    gmail = MagicMock()
    gmail.fetch_recent.return_value = [_mail(), _mail(mid="<b@example.com>", subject="勝間和代の毎日メルマガ #101")]

    slack = MagicMock()
    slack.post_message.return_value = SlackPostResult(
        ok=True, ts="111.222", permalink="https://slack.example/p1"
    )

    now = datetime(2026, 5, 19, 6, 30, tzinfo=timezone.utc)
    posted = ingest_new_mailmagazines(
        cfg, gmail=gmail, slack=slack, store=store, now=now,
        generator=TemplateWorksheetGenerator(),
    )
    assert len(posted) == 2
    assert slack.post_message.call_count == 4

    slack.post_message.reset_mock()
    posted_again = ingest_new_mailmagazines(
        cfg, gmail=gmail, slack=slack, store=store, now=now,
        generator=TemplateWorksheetGenerator(),
    )
    assert posted_again == []
    assert slack.post_message.call_count == 0


def test_ingest_posts_worksheet_in_thread(tmp_path: Path):
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path_resolved)

    gmail = MagicMock()
    gmail.fetch_recent.return_value = [_mail()]

    slack = MagicMock()
    slack.post_message.return_value = SlackPostResult(
        ok=True, ts="111.222", permalink="https://slack.example/p1"
    )

    ingest_new_mailmagazines(
        cfg, gmail=gmail, slack=slack, store=store,
        now=datetime(2026, 5, 19, 6, 30, tzinfo=timezone.utc),
        generator=TemplateWorksheetGenerator(),
    )

    assert slack.post_message.call_count == 2
    parent_call, worksheet_call = slack.post_message.call_args_list
    assert parent_call.kwargs.get("thread_ts") is None
    assert worksheet_call.kwargs.get("thread_ts") == "111.222"
    assert ":pencil:" in worksheet_call.kwargs["text"]
    rendered = str(worksheet_call.kwargs["blocks"])
    assert "今日のワーク" in rendered
    assert "もし自分が同じ状況" in rendered

    rows = store.list_messages()
    assert rows[0].worksheet
    parsed = Worksheet.from_json(rows[0].worksheet)
    assert parsed.questions


def test_ingest_filters_non_matching_sender(tmp_path: Path):
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path_resolved)

    other = FetchedEmail(
        message_id="<spam@example.com>",
        subject="広告: 勝間ではない",
        sender="spam@other.com",
        received_at=datetime(2026, 5, 19, 6, 0, tzinfo=timezone.utc),
        body_text="…",
    )
    gmail = MagicMock()
    gmail.fetch_recent.return_value = [other]
    slack = MagicMock()
    slack.post_message.return_value = SlackPostResult(ok=True)

    posted = ingest_new_mailmagazines(
        cfg, gmail=gmail, slack=slack, store=store,
        now=datetime(2026, 5, 19, 6, 30, tzinfo=timezone.utc),
        generator=TemplateWorksheetGenerator(),
    )
    assert posted == []
    slack.post_message.assert_not_called()


def test_send_due_reminders_includes_review_prompt(tmp_path: Path):
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path_resolved)
    posted_at = datetime(2026, 5, 19, 6, 0, tzinfo=timezone.utc)
    ws = Worksheet(
        case_summary="今日のテーマ: *習慣の力*",
        questions=["Q1: 要約", "Q2: もし自分が同じ状況なら？", "Q3: 一歩は？"],
        action_prompt="返信してね",
    )
    store.insert_message(
        message_id="<a@example.com>",
        subject="勝間和代の毎日メルマガ #100",
        sender="info@kazuyokatsuma.com",
        received_at=posted_at,
        posted_at=posted_at,
        slack_ts="111.222",
        slack_permalink="https://slack.example/p1",
        summary="…",
        intervals_days=cfg.review_intervals_days,
        worksheet=ws.to_json(),
    )

    slack = MagicMock()
    slack.post_message.return_value = SlackPostResult(ok=True, ts="222.333")

    n = send_due_reminders(
        cfg, slack=slack, store=store,
        now=posted_at + timedelta(days=1, hours=1),
    )
    assert n == 1

    call = slack.post_message.call_args
    assert call.kwargs["thread_ts"] == "111.222"
    assert "行動編" in call.kwargs["text"]
    rendered = str(call.kwargs["blocks"])
    assert "行動編" in rendered
    assert "あの日のワーク" in rendered
    assert "もし自分が同じ状況なら？" in rendered


def test_send_due_reminders_marks_sent(tmp_path: Path):
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path_resolved)
    posted_at = datetime(2026, 5, 19, 6, 0, tzinfo=timezone.utc)
    store.insert_message(
        message_id="<a@example.com>",
        subject="勝間和代の毎日メルマガ #100",
        sender="info@kazuyokatsuma.com",
        received_at=posted_at,
        posted_at=posted_at,
        slack_ts="111.222",
        slack_permalink="https://slack.example/p1",
        summary="…",
        intervals_days=cfg.review_intervals_days,
    )

    slack = MagicMock()
    slack.post_message.return_value = SlackPostResult(ok=True, ts="222.333")

    n = send_due_reminders(
        cfg, slack=slack, store=store,
        now=posted_at + timedelta(days=1, hours=1),
    )
    assert n == 1
    n2 = send_due_reminders(
        cfg, slack=slack, store=store,
        now=posted_at + timedelta(days=1, hours=2),
    )
    assert n2 == 0

    n3 = send_due_reminders(
        cfg, slack=slack, store=store,
        now=posted_at + timedelta(days=7, hours=1),
    )
    assert n3 == 2


def test_send_due_reminders_keeps_pending_on_failure(tmp_path: Path):
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path_resolved)
    posted_at = datetime(2026, 5, 19, 6, 0, tzinfo=timezone.utc)
    store.insert_message(
        message_id="<a@example.com>",
        subject="サンプル",
        sender="info@kazuyokatsuma.com",
        received_at=posted_at,
        posted_at=posted_at,
        slack_ts=None,
        slack_permalink=None,
        summary=None,
        intervals_days=[1],
    )

    slack = MagicMock()
    slack.post_message.return_value = SlackPostResult(ok=False, error="bad")

    n = send_due_reminders(
        cfg, slack=slack, store=store,
        now=posted_at + timedelta(days=1, hours=1),
    )
    assert n == 0
    n2 = send_due_reminders(
        cfg, slack=slack, store=store,
        now=posted_at + timedelta(days=1, hours=2),
    )
    assert n2 == 0
