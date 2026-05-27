from datetime import datetime, timedelta, timezone
from pathlib import Path

from katsuma_to_slack.store import Store


def _utc(year: int, month: int, day: int, hour: int = 6) -> datetime:
    return datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc)


def test_insert_and_dedupe(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")

    posted = _utc(2026, 5, 1)
    store.insert_message(
        message_id="<a@example.com>",
        subject="勝間和代の毎日メルマガ #1",
        sender="info@kazuyokatsuma.com",
        received_at=posted,
        posted_at=posted,
        slack_ts=None,
        slack_permalink=None,
        summary="本文の冒頭",
        intervals_days=[1, 3, 7, 30],
    )

    assert store.has_message("<a@example.com>")
    assert not store.has_message("<other@example.com>")


def test_due_reminders_progresses_with_time(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    posted = _utc(2026, 5, 1)
    store.insert_message(
        message_id="<a@example.com>",
        subject="サンプル",
        sender="info@kazuyokatsuma.com",
        received_at=posted,
        posted_at=posted,
        slack_ts="111.222",
        slack_permalink="https://slack.example/p1",
        summary="…",
        intervals_days=[1, 3, 7, 30],
    )

    assert store.due_reminders(posted) == []

    due_day1 = store.due_reminders(posted + timedelta(days=1, hours=1))
    assert [r.interval_days for r in due_day1] == [1]
    assert due_day1[0].slack_permalink == "https://slack.example/p1"
    assert due_day1[0].slack_ts == "111.222"

    store.mark_reminder_sent(due_day1[0].id, posted + timedelta(days=1, hours=1))
    assert store.due_reminders(posted + timedelta(days=1, hours=2)) == []

    due_day7 = store.due_reminders(posted + timedelta(days=7, hours=1))
    assert sorted(r.interval_days for r in due_day7) == [3, 7]


def test_intervals_are_unique_per_message(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    posted = _utc(2026, 5, 1)
    pk = store.insert_message(
        message_id="<a@example.com>",
        subject="サンプル",
        sender="x@y",
        received_at=posted,
        posted_at=posted,
        slack_ts=None,
        slack_permalink=None,
        summary=None,
        intervals_days=[1, 1, 3],
    )
    assert pk > 0
    due = store.due_reminders(posted + timedelta(days=400))
    assert sorted(r.interval_days for r in due) == [1, 3]
