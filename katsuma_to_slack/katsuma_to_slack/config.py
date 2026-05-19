"""環境変数から設定を読み込む."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


def _split_csv_int(value: str) -> List[int]:
    return [int(x.strip()) for x in value.split(",") if x.strip()]


@dataclass
class Config:
    gmail_address: str
    gmail_app_password: str
    gmail_imap_host: str = "imap.gmail.com"
    gmail_imap_port: int = 993
    gmail_mailbox: str = "INBOX"

    katsuma_from: str = "info@kazuyokatsuma.com"
    katsuma_subject_contains: str = ""
    lookback_days: int = 2

    slack_webhook_url: str = ""
    slack_bot_token: Optional[str] = None
    slack_channel_id: Optional[str] = None

    review_intervals_days: List[int] = field(default_factory=lambda: [1, 3, 7, 30])
    remind_hour: int = 8

    db_path: str = "./katsuma.sqlite3"

    # ---- ワーク機能 ---- #
    worksheet_mode: str = "template"  # template | llm | off
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> "Config":
        env = env if env is not None else os.environ

        def get(key: str, default: str = "") -> str:
            return (env.get(key) or default).strip()

        intervals = _split_csv_int(get("REVIEW_INTERVALS_DAYS", "1,3,7,30"))

        return cls(
            gmail_address=get("GMAIL_ADDRESS"),
            gmail_app_password=get("GMAIL_APP_PASSWORD"),
            gmail_imap_host=get("GMAIL_IMAP_HOST", "imap.gmail.com"),
            gmail_imap_port=int(get("GMAIL_IMAP_PORT", "993")),
            gmail_mailbox=get("GMAIL_MAILBOX", "INBOX"),
            katsuma_from=get("KATSUMA_FROM", "info@kazuyokatsuma.com"),
            katsuma_subject_contains=get("KATSUMA_SUBJECT_CONTAINS", ""),
            lookback_days=int(get("LOOKBACK_DAYS", "2")),
            slack_webhook_url=get("SLACK_WEBHOOK_URL"),
            slack_bot_token=get("SLACK_BOT_TOKEN") or None,
            slack_channel_id=get("SLACK_CHANNEL_ID") or None,
            review_intervals_days=intervals,
            remind_hour=int(get("REMIND_HOUR", "8")),
            db_path=get("DB_PATH", "./katsuma.sqlite3"),
            worksheet_mode=get("WORKSHEET_MODE", "template"),
            openai_api_key=get("OPENAI_API_KEY") or None,
            openai_model=get("OPENAI_MODEL", "gpt-4o-mini"),
            openai_base_url=get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )

    def validate(self) -> None:
        missing: List[str] = []
        if not self.gmail_address:
            missing.append("GMAIL_ADDRESS")
        if not self.gmail_app_password:
            missing.append("GMAIL_APP_PASSWORD")
        if not self.slack_webhook_url and not (self.slack_bot_token and self.slack_channel_id):
            missing.append("SLACK_WEBHOOK_URL もしくは SLACK_BOT_TOKEN+SLACK_CHANNEL_ID")
        if missing:
            raise RuntimeError(
                "必要な環境変数が設定されていません: " + ", ".join(missing)
            )

    @property
    def db_path_resolved(self) -> Path:
        return Path(self.db_path).expanduser().resolve()
