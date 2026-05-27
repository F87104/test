"""Gmail から IMAP でメールを取得し, 勝間和代メルマガに該当するものを返す."""

from __future__ import annotations

import email
import imaplib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import Iterable, List, Optional

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


@dataclass
class FetchedEmail:
    message_id: str
    subject: str
    sender: str
    received_at: datetime
    body_text: str

    @property
    def summary(self, max_chars: int = 280) -> str:
        # ノイズになりがちな空行を整理
        text = re.sub(r"\n{3,}", "\n\n", self.body_text).strip()
        return text[:max_chars]


def _decode_header(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n")


def extract_body(msg: Message) -> str:
    """text/plain を優先, なければ text/html を text 化."""
    plain: Optional[str] = None
    html: Optional[str] = None

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except LookupError:
                text = payload.decode("utf-8", errors="replace")
            if ctype == "text/plain" and plain is None:
                plain = text
            elif ctype == "text/html" and html is None:
                html = text
    else:
        payload = msg.get_payload(decode=True)
        if payload is not None:
            charset = msg.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except LookupError:
                text = payload.decode("utf-8", errors="replace")
            if msg.get_content_type() == "text/html":
                html = text
            else:
                plain = text

    if plain:
        return plain
    if html:
        return _html_to_text(html)
    return ""


class GmailClient:
    """ごく薄い IMAP ラッパ. 勝間和代メルマガのフィルタは matches_katsuma() で行う."""

    def __init__(
        self,
        address: str,
        app_password: str,
        host: str = "imap.gmail.com",
        port: int = 993,
        mailbox: str = "INBOX",
    ):
        self.address = address
        self.app_password = app_password
        self.host = host
        self.port = port
        self.mailbox = mailbox

    def _connect(self) -> imaplib.IMAP4_SSL:
        conn = imaplib.IMAP4_SSL(self.host, self.port)
        conn.login(self.address, self.app_password)
        conn.select(self.mailbox, readonly=True)
        return conn

    def fetch_recent(
        self,
        *,
        from_address: str,
        subject_contains: str = "",
        since: Optional[datetime] = None,
    ) -> List[FetchedEmail]:
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=2)

        criteria: List[str] = []
        criteria.append(f'FROM "{from_address}"')
        criteria.append(f'SINCE {since.strftime("%d-%b-%Y")}')
        if subject_contains:
            criteria.append(f'SUBJECT "{subject_contains}"')
        search_query = "(" + " ".join(criteria) + ")"

        emails: List[FetchedEmail] = []
        conn = self._connect()
        try:
            typ, data = conn.search(None, search_query)
            if typ != "OK" or not data or not data[0]:
                return []
            for num in data[0].split():
                typ, msg_data = conn.fetch(num, "(RFC822)")
                if typ != "OK" or not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0][1]
                if not isinstance(raw, (bytes, bytearray)):
                    continue
                msg = email.message_from_bytes(raw)
                fetched = self._to_fetched(msg)
                if fetched is None:
                    continue
                emails.append(fetched)
        finally:
            try:
                conn.close()
            except Exception:
                pass
            conn.logout()
        emails.sort(key=lambda e: e.received_at)
        return emails

    @staticmethod
    def _to_fetched(msg: Message) -> Optional[FetchedEmail]:
        message_id = (msg.get("Message-ID") or "").strip()
        if not message_id:
            return None
        subject = _decode_header(msg.get("Subject"))
        sender = _decode_header(msg.get("From"))
        date_hdr = msg.get("Date")
        try:
            received_at = parsedate_to_datetime(date_hdr) if date_hdr else datetime.now(timezone.utc)
        except (TypeError, ValueError):
            received_at = datetime.now(timezone.utc)
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=timezone.utc)
        body = extract_body(msg)
        return FetchedEmail(
            message_id=message_id,
            subject=subject,
            sender=sender,
            received_at=received_at,
            body_text=body,
        )


def matches_katsuma(
    mail: FetchedEmail,
    *,
    from_address: str,
    subject_contains: str = "",
) -> bool:
    """サーバーサイド検索の補完. 大文字小文字無視で部分一致を見る."""
    sender = mail.sender.lower()
    if from_address and from_address.lower() not in sender:
        return False
    if subject_contains and subject_contains.lower() not in mail.subject.lower():
        return False
    return True
