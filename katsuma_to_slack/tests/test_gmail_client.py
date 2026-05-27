from email.message import EmailMessage

from katsuma_to_slack.gmail_client import (
    FetchedEmail,
    GmailClient,
    extract_body,
    matches_katsuma,
)


def _build_message(*, subject: str, sender: str, body: str, html: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "me@example.com"
    msg["Subject"] = subject
    msg["Message-ID"] = "<unique@id>"
    msg["Date"] = "Mon, 01 Jan 2024 06:00:00 +0900"
    if html is not None:
        msg.set_content(body)
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(body)
    return msg


def test_extract_body_prefers_plain_text():
    msg = _build_message(
        subject="勝間メルマガ #1",
        sender="info@kazuyokatsuma.com",
        body="本文プレーンテキスト",
        html="<html><body><p>HTML本文</p></body></html>",
    )
    assert "本文プレーンテキスト" in extract_body(msg)


def test_extract_body_falls_back_to_html():
    msg = EmailMessage()
    msg["From"] = "x@y"
    msg["Subject"] = "html only"
    msg["Date"] = "Mon, 01 Jan 2024 06:00:00 +0900"
    msg.set_content("<html><body><p>HTML本文</p><script>bad()</script></body></html>", subtype="html")
    body = extract_body(msg)
    assert "HTML本文" in body
    assert "bad()" not in body


def test_to_fetched_decodes_japanese_subject():
    msg = _build_message(
        subject="勝間和代の毎日メルマガ #100",
        sender="勝間和代 <info@kazuyokatsuma.com>",
        body="本日のテーマは…",
    )
    fetched = GmailClient._to_fetched(msg)
    assert fetched is not None
    assert "勝間和代" in fetched.subject
    assert "info@kazuyokatsuma.com" in fetched.sender
    assert fetched.body_text.startswith("本日のテーマは")


def test_matches_katsuma_filters():
    mail = FetchedEmail(
        message_id="<x>",
        subject="勝間和代の毎日メルマガ #100",
        sender="勝間和代 <info@kazuyokatsuma.com>",
        received_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        body_text="…",
    )
    assert matches_katsuma(mail, from_address="info@kazuyokatsuma.com")
    assert matches_katsuma(mail, from_address="info@kazuyokatsuma.com", subject_contains="勝間")
    assert not matches_katsuma(mail, from_address="info@other.com")
    assert not matches_katsuma(mail, from_address="info@kazuyokatsuma.com", subject_contains="株価")
