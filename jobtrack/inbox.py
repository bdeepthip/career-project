"""
Inbox: job emails that update application status automatically.
"""

import os
from datetime import datetime

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)
from sqlalchemy import func

from .auth import login_required
from .email_parser import detect_status, match_application, should_update
from .gmail_sync import fetch_job_emails
from .models import JobApplication, JobEmail, db
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
        and g.user.email == owner
    )


def process_email(user_id, email_data):
    """Save one email, match it to an application, and update that
    application's status if the email moves it forward.

    Returns a note describing what happened, or None if this email
    was already processed (duplicate). The caller commits."""

    message_id = email_data.get("message_id") or f"manual-{datetime.now().timestamp()}"

    if JobEmail.query.filter_by(user_id=user_id, message_id=message_id).first():
        return None

    sender = email_data.get("sender", "")
    subject = email_data.get("subject", "")
    body = email_data.get("body", "")

    detected = detect_status(subject, body)
    applications = JobApplication.query.filter_by(user_id=user_id).all()
    application = match_application(applications, sender, subject, body)

    if application is None:
        note = "No matching application found"
    elif detected is None:
        note = "Matched, but no status found in the email"
    elif should_update(application.status, detected):
        note = f"Status changed: {application.status} -> {detected}"
        application.status = detected
    else:
        note = f"No change (already {application.status})"

    db.session.add(JobEmail(
        user_id=user_id,
        message_id=message_id,
        sender=sender,
        subject=subject,
        body=body,
        received_at=email_data.get("received_at") or datetime.now().strftime("%Y-%m-%d %H:%M"),
        detected_status=detected,
        application_id=application.id if application else None,
        update_note=note,
    ))
    # Make this email visible to the duplicate check above, even before
    # the caller commits (a Gmail sync can contain the same email twice)
    db.session.flush()
    return note


@bp.route("/inbox")
@login_required
def inbox():
    emails = (JobEmail.query.filter_by(user_id=g.user.id)
              .order_by(JobEmail.received_at.desc(), JobEmail.id.desc()).all())

    applications = (JobApplication.query.filter_by(user_id=g.user.id)
                    .order_by(func.lower(JobApplication.company)).all())

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

    note = process_email(g.user.id, email_data)
    db.session.commit()

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

    new_count = updated_count = 0
    for email_data in fetched:
        note = process_email(g.user.id, email_data)
        if note is not None:
            new_count += 1
            if note.startswith("Status changed"):
                updated_count += 1
    db.session.commit()

    flash(f"Synced: {new_count} new email(s), {updated_count} application(s) updated.", "success")
    return redirect(url_for("inbox.inbox"))


@bp.route("/inbox/<int:email_id>/assign", methods=["POST"])
@login_required
def inbox_assign(email_id):
    email_row = JobEmail.query.filter_by(id=email_id, user_id=g.user.id).first()
    application = JobApplication.query.filter_by(
        id=request.form.get("application_id", type=int), user_id=g.user.id
    ).first()

    if email_row is None or application is None:
        abort(404)

    detected = email_row.detected_status
    if should_update(application.status, detected):
        note = f"Status changed: {application.status} -> {detected}"
        application.status = detected
    else:
        note = f"Linked manually (status stays {application.status})"

    email_row.application_id = application.id
    email_row.update_note = note
    db.session.commit()

    flash(note, "success")
    return redirect(url_for("inbox.inbox"))


@bp.route("/inbox/<int:email_id>/delete", methods=["POST"])
@login_required
def inbox_delete(email_id):
    JobEmail.query.filter_by(id=email_id, user_id=g.user.id).delete()
    db.session.commit()
    return redirect(url_for("inbox.inbox"))
