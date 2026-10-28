"""
Incoming email: every user's personal forwarding address.

Each user has an address like jt-7fk2m9qa4xwd@in.example.com. They set
Gmail (or Outlook) to forward job emails there. An email service that
receives mail for that domain posts each email to POST /inbound/email,
and GAJ runs it through the same matching as the Inbox.

Supported senders of the webhook (pick one in production):
  * Cloudflare Email Routing + a small Worker (free): raw email,
    see deploy/cloudflare-email-worker.js
  * Postmark inbound: JSON
  * Mailgun routes ("forward") or SendGrid Inbound Parse: form fields

The webhook is protected by INBOUND_WEBHOOK_SECRET, sent as the password
of the URL (https://jobtrack:SECRET@host/inbound/email), an
X-JobTrack-Secret header, or ?key=SECRET.
"""

import hashlib
import hmac
import html
import json
import re
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses

from flask import Blueprint, abort, current_app, g, jsonify, redirect, request, url_for, flash

from .auth import login_required
from .extensions import limiter
from .inbox import inbound_enabled, process_email
from .models import JobEmail, User, db, new_inbound_token

bp = Blueprint("inbound", __name__)

MAX_BODY_CHARS = 20000
# Addresses look like gaj-<token>@domain. "jt-" was the prefix before the
# app was renamed; still accepted so no forwarding setup ever breaks.
ADDRESS_PREFIXES = ("gaj-", "jt-")
GMAIL_CONFIRM_SENDER = "forwarding-noreply@google.com"


# ---------- Addresses ----------

def find_user(recipients):
    """Return the user whose address is among the recipients, or None."""
    domain = current_app.config["INBOUND_DOMAIN"]
    addresses = []
    for header in recipients:
        # One header at a time: Python rejects the whole list if any
        # single entry is empty or malformed
        if isinstance(header, str) and header.strip():
            addresses += [address for _, address in getaddresses([header])]
    for address in addresses:
        local, _, addr_domain = address.strip().lower().rpartition("@")
        prefix = next((p for p in ADDRESS_PREFIXES if local.startswith(p)), None)
        if addr_domain != domain or prefix is None:
            continue
        token = local[len(prefix):].split("+", 1)[0]  # allow gaj-token+anything@
        if token:
            user = User.query.filter_by(inbound_token=token).first()
            if user is not None:
                return user
    return None


# ---------- Turning each provider's format into one shape ----------

def html_to_text(markup):
    markup = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", markup or "")
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", text)).strip()


def _from_raw(raw_bytes, envelope_to):
    msg = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    plain = msg.get_body(preferencelist=("plain",))
    rich = msg.get_body(preferencelist=("html",))
    if plain is not None:
        body = plain.get_content()
    elif rich is not None:
        body = html_to_text(rich.get_content())
    else:
        body = ""
    recipients = [envelope_to] if envelope_to else []
    for header in ("Delivered-To", "X-Original-To", "To", "Cc"):
        recipients += [str(v) for v in msg.get_all(header, [])]
    return {
        "recipients": recipients,
        "sender": str(msg.get("From", "")),
        "subject": str(msg.get("Subject", "")),
        "body": body,
        "message_id": str(msg.get("Message-ID", "")),
    }


def _from_postmark(data):
    headers = {h.get("Name", "").lower(): h.get("Value", "") for h in data.get("Headers") or []}
    recipients = [data.get("OriginalRecipient", ""), data.get("To", ""), data.get("Cc", "")]
    recipients += [r.get("Email", "") for r in data.get("ToFull") or []]
    return {
        "recipients": recipients,
        "sender": data.get("From", ""),
        "subject": data.get("Subject", ""),
        "body": data.get("TextBody") or html_to_text(data.get("HtmlBody", "")),
        "message_id": headers.get("message-id", ""),
    }


def _from_form(form):
    # Mailgun: recipient, from, subject, body-plain, Message-Id
    # SendGrid: to, from, subject, text, html, headers, envelope
    recipients = [form.get("recipient", ""), form.get("to", ""), form.get("cc", "")]
    try:
        recipients += json.loads(form.get("envelope") or "{}").get("to") or []
    except (ValueError, AttributeError):
        pass
    message_id = form.get("Message-Id", "")
    if not message_id:
        found = re.search(r"(?im)^message-id:\s*(\S+)", form.get("headers", ""))
        message_id = found.group(1) if found else ""
    body = form.get("body-plain") or form.get("text") or html_to_text(
        form.get("body-html") or form.get("html", ""))
    return {
        "recipients": recipients,
        "sender": form.get("from") or form.get("sender", ""),
        "subject": form.get("subject", ""),
        "body": body,
        "message_id": message_id,
    }


def parse_request():
    if request.mimetype == "application/json":
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return None
        return _from_postmark(data)
    if request.mimetype in ("message/rfc822", "application/octet-stream", "text/plain"):
        envelope_to = request.headers.get("X-Envelope-To") or request.args.get("to", "")
        return _from_raw(request.get_data(), envelope_to)
    if request.form:
        return _from_form(request.form)
    return None


# ---------- The webhook ----------

def secret_ok():
    expected = current_app.config["INBOUND_WEBHOOK_SECRET"]
    candidates = [
        request.headers.get("X-JobTrack-Secret", ""),
        request.args.get("key", ""),
        request.authorization.password if request.authorization else "",
    ]
    return any(c and hmac.compare_digest(c.encode(), expected.encode()) for c in candidates)


@bp.before_request
def allow_bigger_bodies():
    # Emails with attachments (an offer letter PDF) can be several MB.
    # We ignore attachments, but must accept the request to read the text.
    if request.endpoint == "inbound.receive":
        request.max_content_length = 25 * 1024 * 1024


@bp.route("/inbound/email", methods=["POST"])
@limiter.limit("600 per minute")
def receive():
    if not inbound_enabled():
        abort(404)
    if not secret_ok():
        return jsonify(status="unauthorized"), 401

    email_data = parse_request()
    if email_data is None:
        return jsonify(status="unreadable"), 400

    # From here on always answer 200, so the email service doesn't keep retrying
    user = find_user(email_data.pop("recipients"))
    if user is None:
        return jsonify(status="ignored", reason="unknown address")

    today = datetime.now().strftime("%Y-%m-%d")
    received_today = JobEmail.query.filter(
        JobEmail.user_id == user.id, JobEmail.received_at.like(f"{today}%")).count()
    if received_today >= current_app.config["INBOUND_DAILY_LIMIT"]:
        return jsonify(status="ignored", reason="daily limit reached")

    email_data = {k: (v or "").strip() for k, v in email_data.items()}
    email_data["sender"] = email_data["sender"][:300]
    email_data["subject"] = email_data["subject"][:500]
    email_data["body"] = email_data["body"][:MAX_BODY_CHARS]
    if not email_data["message_id"]:
        # Same email delivered twice (a retry) gets the same id, so it's saved once
        fingerprint = "\n".join([email_data["sender"], email_data["subject"], email_data["body"]])
        email_data["message_id"] = "sha256-" + hashlib.sha256(fingerprint.encode()).hexdigest()

    if GMAIL_CONFIRM_SENDER in email_data["sender"].lower():
        saved = save_gmail_confirmation(user.id, email_data)
    else:
        saved = process_email(user.id, email_data, notify_user=True) is not None
    db.session.commit()

    return jsonify(status="processed" if saved else "duplicate")


def save_gmail_confirmation(user_id, email_data):
    """Gmail asks the new forwarding address to confirm. Show the code in
    the Inbox instead of treating it as a job email."""
    if JobEmail.query.filter_by(user_id=user_id, message_id=email_data["message_id"]).first():
        return False
    code = re.search(r"(?i)confirmation code:\s*(\d+)", email_data["body"])
    note = (f"Gmail forwarding confirmation code: {code.group(1)}. Enter it in Gmail settings "
            "to finish setting up forwarding." if code else
            "Gmail sent a forwarding confirmation. Open Gmail settings to finish setup.")
    from .notifications import notify
    notify(user_id, "inbox", note, link=url_for("inbox.inbox"))
    db.session.add(JobEmail(
        user_id=user_id, message_id=email_data["message_id"],
        sender=email_data["sender"], subject=email_data["subject"], body=email_data["body"],
        received_at=datetime.now().strftime("%Y-%m-%d %H:%M"), update_note=note,
    ))
    return True


# ---------- User actions ----------

@bp.route("/inbox/address/new", methods=["POST"])
@login_required
def new_address():
    """Replace the address (if it leaked and spam arrives). The old one stops working."""
    g.user.inbound_token = new_inbound_token()
    db.session.commit()
    flash("You have a new forwarding address. Update it in your Gmail forwarding settings.", "success")
    return redirect(url_for("inbox.inbox"))
