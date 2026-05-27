"""取り込み & リマインダー送信のメインロジック (CLI から呼ぶ).

ingest:
  Gmail から新着メルマガを取り出し、Slack に投稿。直後に「今日のワーク」を
  スレッド（Bot Token があれば）or 同一チャンネル（Webhook 単体）に投げて、
  読者が *自分ごと化の問い* に答えやすい形にする。

remind:
  期限到来の復習リマインダーを Slack に流す。interval ごとに「行動編 / 経過編 /
  習慣化編 / 振り返り編」と異なる視点の問いを出し、同時にあの日のワークの
  問いも添える（参照用）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from .config import Config
from .gmail_client import FetchedEmail, GmailClient, matches_katsuma
from .slack_client import (
    SlackPoster,
    build_mailmagazine_blocks,
    build_reminder_blocks,
    build_worksheet_blocks,
)
from .store import Store
from .worksheet import (
    Worksheet,
    WorksheetGenerator,
    build_generator,
    review_prompt_for,
)


logger = logging.getLogger(__name__)


def _format_jst(dt: datetime) -> str:
    jst = timezone(timedelta(hours=9))
    return dt.astimezone(jst).strftime("%Y-%m-%d %H:%M JST")


def _build_default_generator(cfg: Config) -> WorksheetGenerator:
    return build_generator(
        mode=cfg.worksheet_mode,
        openai_api_key=cfg.openai_api_key,
        openai_model=cfg.openai_model,
        openai_base_url=cfg.openai_base_url,
    )


def _post_worksheet(
    *,
    slack: SlackPoster,
    worksheet: Worksheet,
    parent_ts: Optional[str],
) -> None:
    if not worksheet.questions:
        return
    blocks = build_worksheet_blocks(worksheet=worksheet)
    text = ":pencil: 今日のワーク"
    result = slack.post_message(text=text, blocks=blocks, thread_ts=parent_ts)
    if not result.ok:
        logger.error("ワーク投稿失敗: %s", result.error)


def ingest_new_mailmagazines(
    cfg: Config,
    *,
    gmail: GmailClient | None = None,
    slack: SlackPoster | None = None,
    store: Store | None = None,
    generator: WorksheetGenerator | None = None,
    now: datetime | None = None,
) -> List[FetchedEmail]:
    """Gmail を見て, 未取り込みの勝間メルマガを Slack に投稿し DB に保存する."""
    cfg.validate()
    now = now or datetime.now(timezone.utc)

    gmail = gmail or GmailClient(
        address=cfg.gmail_address,
        app_password=cfg.gmail_app_password,
        host=cfg.gmail_imap_host,
        port=cfg.gmail_imap_port,
        mailbox=cfg.gmail_mailbox,
    )
    slack = slack or SlackPoster(
        webhook_url=cfg.slack_webhook_url,
        bot_token=cfg.slack_bot_token,
        channel_id=cfg.slack_channel_id,
    )
    store = store or Store(cfg.db_path_resolved)
    generator = generator or _build_default_generator(cfg)

    since = now - timedelta(days=cfg.lookback_days)
    fetched = gmail.fetch_recent(
        from_address=cfg.katsuma_from,
        subject_contains=cfg.katsuma_subject_contains,
        since=since,
    )
    logger.info("Gmail から %d 件取得", len(fetched))

    posted: List[FetchedEmail] = []
    for mail in fetched:
        if not matches_katsuma(
            mail,
            from_address=cfg.katsuma_from,
            subject_contains=cfg.katsuma_subject_contains,
        ):
            continue
        if store.has_message(mail.message_id):
            logger.debug("既に投稿済み: %s", mail.subject)
            continue

        blocks = build_mailmagazine_blocks(
            subject=mail.subject,
            sender=mail.sender,
            received_at_str=_format_jst(mail.received_at),
            summary=mail.summary,
        )
        result = slack.post_message(text=f":books: {mail.subject}", blocks=blocks)
        if not result.ok:
            logger.error("Slack 投稿失敗: %s / %s", mail.subject, result.error)
            continue

        worksheet = generator.generate(subject=mail.subject, body=mail.body_text)
        worksheet_json: Optional[str] = None
        if worksheet.questions:
            worksheet_json = worksheet.to_json()
            _post_worksheet(slack=slack, worksheet=worksheet, parent_ts=result.ts)

        store.insert_message(
            message_id=mail.message_id,
            subject=mail.subject,
            sender=mail.sender,
            received_at=mail.received_at,
            posted_at=now,
            slack_ts=result.ts,
            slack_permalink=result.permalink,
            summary=mail.summary,
            intervals_days=cfg.review_intervals_days,
            worksheet=worksheet_json,
        )
        posted.append(mail)
        logger.info("投稿完了: %s", mail.subject)

    return posted


def send_due_reminders(
    cfg: Config,
    *,
    slack: SlackPoster | None = None,
    store: Store | None = None,
    now: datetime | None = None,
) -> int:
    """期限が来たリマインダーを Slack に流す. 送った件数を返す."""
    cfg.validate()
    now = now or datetime.now(timezone.utc)
    slack = slack or SlackPoster(
        webhook_url=cfg.slack_webhook_url,
        bot_token=cfg.slack_bot_token,
        channel_id=cfg.slack_channel_id,
    )
    store = store or Store(cfg.db_path_resolved)

    due = store.due_reminders(now)
    sent = 0
    for r in due:
        review = review_prompt_for(r.interval_days)
        original_questions: List[str] = []
        if r.worksheet:
            try:
                original_questions = Worksheet.from_json(r.worksheet).questions
            except Exception as exc:
                logger.warning("worksheet JSON parse failed: %s", exc)
        blocks = build_reminder_blocks(
            subject=r.subject,
            interval_days=r.interval_days,
            permalink=r.slack_permalink,
            review=review,
            original_questions=original_questions,
        )
        text = f":alarm_clock: {review.label}: {r.subject}"
        result = slack.post_message(
            text=text,
            blocks=blocks,
            thread_ts=r.slack_ts,
        )
        if not result.ok:
            logger.error("リマインダー投稿失敗: %s / %s", r.subject, result.error)
            continue
        store.mark_reminder_sent(r.id, now)
        sent += 1
        logger.info("リマインダー送信: %sd / %s", r.interval_days, r.subject)
    return sent
