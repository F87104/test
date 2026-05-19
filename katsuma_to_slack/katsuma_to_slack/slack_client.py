"""Slack への投稿. Incoming Webhook を基本とし, Bot Token があれば API を併用する."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api"


@dataclass
class SlackPostResult:
    ok: bool
    ts: Optional[str] = None
    permalink: Optional[str] = None
    error: Optional[str] = None


def build_mailmagazine_blocks(
    *,
    subject: str,
    sender: str,
    received_at_str: str,
    summary: str,
) -> List[Dict[str, Any]]:
    """メルマガ本体を投稿するときの Block Kit ブロック."""
    snippet = summary if len(summary) <= 2800 else summary[:2800] + "…(続く)"
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f":books: {subject}"[:150]},
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"*From:* {sender}"},
                {"type": "mrkdwn", "text": f"*Received:* {received_at_str}"},
            ],
        },
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": snippet}},
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        ":speech_balloon: このスレッドに *自分の意見・気付き・実行したいこと* "
                        "を返信してメモしましょう。1日 / 3日 / 7日 / 30日後に復習通知が届きます。"
                    ),
                },
            ],
        },
    ]


def build_reminder_blocks(
    *,
    subject: str,
    interval_days: int,
    permalink: Optional[str],
) -> List[Dict[str, Any]]:
    head = f":alarm_clock: {interval_days}日後の復習: {subject}"[:150]
    if permalink:
        body = (
            f"<{permalink}|あの日のメルマガをもう一度読み返しましょう。>\n"
            "*いま振り返って思うことを、このスレッドに追記してください。*"
        )
    else:
        body = (
            f"*{subject}*\n"
            "あの日のメルマガをもう一度読み返しましょう。\n"
            "*いま振り返って思うことを、このスレッドに追記してください。*"
        )
    return [
        {"type": "header", "text": {"type": "plain_text", "text": head}},
        {"type": "section", "text": {"type": "mrkdwn", "text": body}},
    ]


class SlackPoster:
    def __init__(
        self,
        webhook_url: str = "",
        bot_token: Optional[str] = None,
        channel_id: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ):
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.session = session or requests.Session()

    def post_message(
        self,
        *,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None,
    ) -> SlackPostResult:
        """Bot Token があれば chat.postMessage, なければ Incoming Webhook を使う."""
        if self.bot_token and self.channel_id:
            return self._post_via_api(text=text, blocks=blocks, thread_ts=thread_ts)
        return self._post_via_webhook(text=text, blocks=blocks)

    def _post_via_api(
        self,
        *,
        text: str,
        blocks: Optional[List[Dict[str, Any]]],
        thread_ts: Optional[str],
    ) -> SlackPostResult:
        payload: Dict[str, Any] = {"channel": self.channel_id, "text": text}
        if blocks:
            payload["blocks"] = blocks
        if thread_ts:
            payload["thread_ts"] = thread_ts
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        resp = self.session.post(
            f"{SLACK_API}/chat.postMessage", headers=headers, json=payload, timeout=20
        )
        try:
            data = resp.json()
        except ValueError:
            return SlackPostResult(ok=False, error=f"non-json response: {resp.text[:200]}")
        if not data.get("ok"):
            return SlackPostResult(ok=False, error=str(data.get("error")))
        ts = data.get("ts")
        permalink = self._fetch_permalink(ts) if ts else None
        return SlackPostResult(ok=True, ts=ts, permalink=permalink)

    def _post_via_webhook(
        self,
        *,
        text: str,
        blocks: Optional[List[Dict[str, Any]]],
    ) -> SlackPostResult:
        if not self.webhook_url:
            return SlackPostResult(ok=False, error="no webhook url")
        payload: Dict[str, Any] = {"text": text}
        if blocks:
            payload["blocks"] = blocks
        resp = self.session.post(self.webhook_url, json=payload, timeout=20)
        if resp.status_code >= 300:
            return SlackPostResult(ok=False, error=f"http {resp.status_code}: {resp.text[:200]}")
        return SlackPostResult(ok=True)

    def _fetch_permalink(self, ts: str) -> Optional[str]:
        if not (self.bot_token and self.channel_id):
            return None
        try:
            resp = self.session.get(
                f"{SLACK_API}/chat.getPermalink",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                params={"channel": self.channel_id, "message_ts": ts},
                timeout=20,
            )
            data = resp.json()
            if data.get("ok"):
                return data.get("permalink")
            logger.warning("getPermalink failed: %s", data.get("error"))
        except Exception as exc:
            logger.warning("getPermalink error: %s", exc)
        return None
