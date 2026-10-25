"""
Fetches job emails from one Gmail label using IMAP.

Setup (one time):
1. Turn on 2-Step Verification for your Google account.
2. Create an App Password: Google Account -> Security -> App passwords.
3. In Gmail, create a label called "JobTrack" and a filter that
   applies it to job emails (from greenhouse, lever, workday, etc.).
4. Add these lines to your .env file (never commit .env):
       EMAIL_ADDRESS=you@gmail.com
       EMAIL_APP_PASSWORD=the16charpassword
       IMAP_FOLDER=JobTrack

This reads ONLY the JobTrack label, and opens it read-only, so it
never changes or deletes anything in your mailbox.

Note: this works for one person (you) because the password lives in
your own .env file. A public multi-user app would need Google OAuth
instead, which requires Google's app review.
"""

import email
import imaplib
import os
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime


IMAP_HOST = "imap.gmail.com"


def _decode(value):
    """Turn encoded headers like '=?UTF-8?...' into normal text."""

    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _get_body(message):
    """Return the plain-text body of an email."""

    if message.is_multipart():
        for part in message.walk():
            disposition = str(part.get("Content-Disposition") or "")
            if (
                part.get_content_type() == "text/plain"
                and "attachment" not in disposition
            ):
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        return ""

    payload = message.get_payload(decode=True) or b""
    charset = message.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def fetch_job_emails(limit=50):
    """Return the newest job emails as a list of dicts:
    message_id, sender, subject, body, received_at.

    Raises RuntimeError with a readable message if setup is missing.
    """

    address = os.environ.get("EMAIL_ADDRESS")
    password = os.environ.get("EMAIL_APP_PASSWORD")
    folder = os.environ.get("IMAP_FOLDER", "JobTrack")

    if not address or not password:
        raise RuntimeError(
            "Gmail is not set up. Add EMAIL_ADDRESS and "
            "EMAIL_APP_PASSWORD to your .env file."
        )

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(address, password)
    except imaplib.IMAP4.error:
        raise RuntimeError(
            "Gmail login failed. Check EMAIL_ADDRESS and that "
            "EMAIL_APP_PASSWORD is an App Password, not your normal password."
        )

    try:
        # readonly=True: never marks emails as read or changes anything
        status, _ = mail.select(f'"{folder}"', readonly=True)
        if status != "OK":
            raise RuntimeError(
                f'Gmail label "{folder}" was not found. '
                "Create it in Gmail or fix IMAP_FOLDER in .env."
            )

        status, data = mail.search(None, "ALL")
        ids = data[0].split()[-limit:] if status == "OK" else []

        emails = []

        for email_id in ids:
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            message = email.message_from_bytes(msg_data[0][1])

            try:
                received = parsedate_to_datetime(message.get("Date"))
                received_at = received.strftime("%Y-%m-%d %H:%M")
            except (TypeError, ValueError):
                received_at = ""

            emails.append({
                "message_id": message.get("Message-ID") or f"imap-{email_id.decode()}",
                "sender": _decode(message.get("From")),
                "subject": _decode(message.get("Subject")),
                "body": _get_body(message)[:5000],
                "received_at": received_at,
            })

        return emails

    finally:
        try:
            mail.logout()
        except Exception:
            pass
