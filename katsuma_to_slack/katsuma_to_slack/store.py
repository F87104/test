"""SQLite による永続化: 取り込んだメールと、それに紐づく復習リマインダー & ワークを管理."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE NOT NULL,
    subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    received_at TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    slack_ts TEXT,
    slack_permalink TEXT,
    summary TEXT,
    worksheet TEXT
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_pk INTEGER NOT NULL,
    interval_days INTEGER NOT NULL,
    due_at TEXT NOT NULL,
    sent_at TEXT,
    UNIQUE(message_pk, interval_days),
    FOREIGN KEY(message_pk) REFERENCES messages(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reminders_due
    ON reminders(due_at)
    WHERE sent_at IS NULL;
"""


@dataclass
class MessageRow:
    id: int
    message_id: str
    subject: str
    sender: str
    received_at: datetime
    posted_at: datetime
    slack_ts: Optional[str]
    slack_permalink: Optional[str]
    summary: Optional[str]
    worksheet: Optional[str] = None


@dataclass
class ReminderRow:
    id: int
    message_pk: int
    interval_days: int
    due_at: datetime
    sent_at: Optional[datetime]
    subject: str = ""
    slack_permalink: Optional[str] = None
    slack_ts: Optional[str] = None
    worksheet: Optional[str] = None


def _to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    """既存DBに後付けでカラムを追加する (idempotent)."""
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


class Store:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            _ensure_column(conn, "messages", "worksheet", "TEXT")

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def has_message(self, message_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM messages WHERE message_id = ?", (message_id,)
            ).fetchone()
            return row is not None

    def insert_message(
        self,
        *,
        message_id: str,
        subject: str,
        sender: str,
        received_at: datetime,
        posted_at: datetime,
        slack_ts: Optional[str],
        slack_permalink: Optional[str],
        summary: Optional[str],
        intervals_days: Iterable[int],
        worksheet: Optional[str] = None,
    ) -> int:
        """メールと復習リマインダーをまとめて登録. messages.id を返す."""
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO messages
                    (message_id, subject, sender, received_at, posted_at,
                     slack_ts, slack_permalink, summary, worksheet)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    subject,
                    sender,
                    _to_iso(received_at),
                    _to_iso(posted_at),
                    slack_ts,
                    slack_permalink,
                    summary,
                    worksheet,
                ),
            )
            pk = cur.lastrowid
            for d in intervals_days:
                due = posted_at + timedelta(days=int(d))
                conn.execute(
                    """
                    INSERT OR IGNORE INTO reminders
                        (message_pk, interval_days, due_at)
                    VALUES (?, ?, ?)
                    """,
                    (pk, int(d), _to_iso(due)),
                )
            return pk

    def due_reminders(self, now: datetime) -> List[ReminderRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT r.id, r.message_pk, r.interval_days, r.due_at, r.sent_at,
                       m.subject, m.slack_permalink, m.slack_ts, m.worksheet
                FROM reminders r
                JOIN messages m ON m.id = r.message_pk
                WHERE r.sent_at IS NULL AND r.due_at <= ?
                ORDER BY r.due_at ASC
                """,
                (_to_iso(now),),
            ).fetchall()
        return [
            ReminderRow(
                id=row["id"],
                message_pk=row["message_pk"],
                interval_days=row["interval_days"],
                due_at=_from_iso(row["due_at"]),
                sent_at=_from_iso(row["sent_at"]) if row["sent_at"] else None,
                subject=row["subject"] or "",
                slack_permalink=row["slack_permalink"],
                slack_ts=row["slack_ts"],
                worksheet=row["worksheet"],
            )
            for row in rows
        ]

    def mark_reminder_sent(self, reminder_id: int, sent_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE reminders SET sent_at = ? WHERE id = ?",
                (_to_iso(sent_at), reminder_id),
            )

    def list_messages(self, limit: int = 50) -> List[MessageRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, message_id, subject, sender, received_at, posted_at,
                       slack_ts, slack_permalink, summary, worksheet
                FROM messages
                ORDER BY received_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            MessageRow(
                id=row["id"],
                message_id=row["message_id"],
                subject=row["subject"],
                sender=row["sender"],
                received_at=_from_iso(row["received_at"]),
                posted_at=_from_iso(row["posted_at"]),
                slack_ts=row["slack_ts"],
                slack_permalink=row["slack_permalink"],
                summary=row["summary"],
                worksheet=row["worksheet"],
            )
            for row in rows
        ]
