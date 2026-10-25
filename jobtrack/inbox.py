"""
Inbox: job emails that update application status automatically.
"""

import os
from datetime import datetime

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)

from .auth import login_required
from .db import get_db
from .email_parser import detect_status, match_application, should_update
from .gmail_sync import fetch_job_emails
from .validation import clean

bp = Blueprint("inbox", __name__)


def gmail_sync_allowed():
    """Gmail sync reads ONE mailbox: the one in .env. Only the account
    whose email matches EMAIL_ADDRESS may use it. Without this check,
    any user who signed up could import that mailbox into their own
    account. Other users get per-user forwarding addresses (phase 4)."""

    owner = (os.environ.get("EMAIL_ADDRESS") or "").strip().lower()
    return bool(
        owner
        and os.environ.get("EMAIL_APP_PASSWORD")
        and g.user is not None
        and g.user["email"] == owner
    )


def process_email(db, user_id, email_data):
    """Save one email, match it to an application, and update that
    application's status if the email moves it forward.

    Returns a note describing what happened, or None if this email
    was already processed (duplicate)."""

    message_id = email_data.get("message_id") or f"manual-{datetime.now().timestamp()}"

    if db.execute(
        "SELECT 1 FROM job_emails WHERE user_id = ? AND message_id = ?",
        (user_id, message_id),
    ).fetchone():
        return None

    sender = email_data.get("sender", "")
    subject = email_data.get("subject", "")
    body = email_data.get("body", "")

    detected = detect_status(subject, body)
    applications = db.execute(
        "SELECT * FROM job_applications WHERE user_id = ?", (user_id,)
    ).fetchall()
    application = match_application(applications, sender, subject, body)

    if application is None:
        note = "No matching application found"
    elif detected is None:
        note = "Matched, but no status found in the email"
    elif should_update(application["status"], detected):
        db.execute(
            "UPDATE job_applications SET status = ? WHERE id = ? AND user_id = ?",
            (detected, application["id"], user_id),
        )
        note = f"Status changed: {application['status']} -> {detected}"
    else:
        note = f"No change (already {application['status']})"

    db.execute(
        """
        INSERT INTO job_emails
        (user_id, message_id, sender, subject, body, received_at,
         detected_status, application_id, update_note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, message_id, sender, subject, body,
         email_data.get("received_at") or datetime.now().strftime("%Y-%m-%d %H:%M"),
         detected, application["id"] if application else None, note),
    )
    return note


@bp.route("/inbox")
@login_required
def inbox():
    db = get_db()
    user_id = g.user["id"]

    emails = db.execute(
        """
        SELECT job_emails.*,
               job_applications.company AS app_company,
               job_applications.job_title AS app_title
        FROM job_emails
        LEFT JOIN job_applications
            ON job_emails.application_id = job_applications.id
           AND job_applications.user_id = job_emails.user_id
        WHERE job_emails.user_id = ?
        ORDER BY job_emails.received_at DESC, job_emails.id DESC
        """,
        (user_id,),
    ).fetchall()

    applications = db.execute(
        """
        SELECT id, company, job_title, status
        FROM job_applications WHERE user_id = ?
        ORDER BY company COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()

    return render_template(
        "inbox/inbox.html",
        emails=emails,
        applications=applications,
        gmail_enabled=gmail_sync_allowed(),
    )


@bp.route("/inbox/add", methods=["POST"])
@login_required
def inbox_add():
    email_data = {
        "sender": clean(request.form, "sender", 300),
        "subject": clean(request.form, "subject", 500),
        "body": clean(request.form, "body", 20000),
    }

    if not email_data["subject"] and not email_data["body"]:
        flash("Paste at least a subject or the email text.", "error")
        return redirect(url_for("inbox.inbox"))

    db = get_db()
    note = process_email(db, g.user["id"], email_data)
    db.commit()

    flash(note or "This email was already processed.", "success")
    return redirect(url_for("inbox.inbox"))


@bp.route("/inbox/sync", methods=["POST"])
@login_required
def inbox_sync():
    if not gmail_sync_allowed():
        abort(403)

    try:
        fetched = fetch_job_emails()
    except RuntimeError as error:
        flash(str(error), "error")
        return redirect(url_for("inbox.inbox"))
    except OSError:
        flash("Couldn't reach Gmail. Check your internet connection and try again.", "error")
        return redirect(url_for("inbox.inbox"))

    db = get_db()
    new_count = updated_count = 0
    for email_data in fetched:
        note = process_email(db, g.user["id"], email_data)
        if note is not None:
            new_count += 1
            if note.startswith("Status changed"):
                updated_count += 1
    db.commit()

    flash(f"Synced: {new_count} new email(s), {updated_count} application(s) updated.", "success")
    return redirect(url_for("inbox.inbox"))


@bp.route("/inbox/<int:email_id>/assign", methods=["POST"])
@login_required
def inbox_assign(email_id):
    db = get_db()
    user_id = g.user["id"]

    email_row = db.execute(
        "SELECT * FROM job_emails WHERE id = ? AND user_id = ?", (email_id, user_id)
    ).fetchone()
    application = db.execute(
        "SELECT * FROM job_applications WHERE id = ? AND user_id = ?",
        (request.form.get("application_id", type=int), user_id),
    ).fetchone()

    if email_row is None or application is None:
        abort(404)

    detected = email_row["detected_status"]
    if should_update(application["status"], detected):
        db.execute(
            "UPDATE job_applications SET status = ? WHERE id = ? AND user_id = ?",
            (detected, application["id"], user_id),
        )
        note = f"Status changed: {application['status']} -> {detected}"
    else:
        note = f"Linked manually (status stays {application['status']})"

    db.execute(
        "UPDATE job_emails SET application_id = ?, update_note = ? WHERE id = ? AND user_id = ?",
        (application["id"], note, email_id, user_id),
    )
    db.commit()

    flash(note, "success")
    return redirect(url_for("inbox.inbox"))


@bp.route("/inbox/<int:email_id>/delete", methods=["POST"])
@login_required
def inbox_delete(email_id):
    db = get_db()
    db.execute("DELETE FROM job_emails WHERE id = ? AND user_id = ?", (email_id, g.user["id"]))
    db.commit()
    return redirect(url_for("inbox.inbox"))
