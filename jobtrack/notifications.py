"""
Notifications: a list of things that happened while you were away
(new messages, application status changes, your forwarding setup...).
Other modules call notify(); the caller commits.
"""

from datetime import datetime, timezone

from flask import Blueprint, abort, g, redirect, render_template, url_for

from .auth import login_required
from .models import Message, Notification, db

bp = Blueprint("notifications", __name__)

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
KEEP_PER_USER = 200


def utc_now():
    return datetime.now(timezone.utc).strftime(TIME_FORMAT)


def notify(user_id, kind, text, link=None, replace_unread_link=False):
    """Add a notification. With replace_unread_link, an unread notification
    with the same link is updated instead (five messages from one person
    show as one line, not five)."""
    if replace_unread_link and link:
        existing = Notification.query.filter_by(user_id=user_id, link=link, read_at=None).first()
        if existing is not None:
            existing.text = text
            existing.created_at = utc_now()
            return existing
    note = Notification(user_id=user_id, kind=kind, text=text[:300], link=link, created_at=utc_now())
    db.session.add(note)
    return note


@bp.app_context_processor
def unread_counts():
    if not getattr(g, "user", None):
        return {}
    return {
        "unread_notifications": Notification.query.filter_by(user_id=g.user.id, read_at=None).count(),
        "unread_messages": Message.query.filter_by(recipient_id=g.user.id, read_at=None).count(),
    }


@bp.route("/notifications")
@login_required
def notifications():
    items = (Notification.query.filter_by(user_id=g.user.id)
             .order_by(Notification.created_at.desc(), Notification.id.desc())
             .limit(KEEP_PER_USER).all())
    return render_template("notifications/notifications.html", items=items)


@bp.route("/notifications/<int:note_id>/open", methods=["POST"])
@login_required
def open_notification(note_id):
    note = Notification.query.filter_by(id=note_id, user_id=g.user.id).first()
    if note is None:
        abort(404)
    note.read_at = note.read_at or utc_now()
    db.session.commit()
    # Links are always GAJ paths we wrote ourselves; never redirect elsewhere
    link = note.link if note.link and note.link.startswith("/") and not note.link.startswith("//") else None
    return redirect(link or url_for("notifications.notifications"))


@bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=g.user.id, read_at=None).update({"read_at": utc_now()})
    db.session.commit()
    return redirect(url_for("notifications.notifications"))
