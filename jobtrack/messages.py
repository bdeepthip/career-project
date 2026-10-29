"""
Messages: direct messages between GAJ users (referrals, study partners,
job-search buddies, and later recruiters and applicants).

- Start a conversation by typing someone's account email.
- Block someone: neither of you can message the other any more.
- Report someone: the GAJ team gets an email and the person is blocked.
"""

from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
)
from sqlalchemy import and_, or_

from .auth import login_required
from .extensions import limiter, user_key
from .mailer import send_email
from .models import Block, Message, Notification, Report, User, db
from .notifications import notify, utc_now
from .validation import clean

bp = Blueprint("messages", __name__)

MAX_LENGTH = 2000


def between(a, b):
    """Filter for messages in the conversation between users a and b."""
    return or_(and_(Message.sender_id == a, Message.recipient_id == b),
               and_(Message.sender_id == b, Message.recipient_id == a))


def blocked_either_way(a, b):
    return Block.query.filter(or_(and_(Block.blocker_id == a, Block.blocked_id == b),
                                  and_(Block.blocker_id == b, Block.blocked_id == a))).first() is not None


def have_talked(a, b):
    return Message.query.filter(between(a, b)).first() is not None


def send_message(sender, recipient, body):
    """Save a message and notify the recipient. Returns an error string or None."""
    body = body.strip()[:MAX_LENGTH]
    if not body:
        return "Write a message first."
    if recipient.id == sender.id:
        return "You can't message yourself."
    if blocked_either_way(sender.id, recipient.id):
        return "You can't message this person."
    db.session.add(Message(sender_id=sender.id, recipient_id=recipient.id,
                           body=body, created_at=utc_now()))
    preview = body if len(body) <= 80 else body[:77] + "..."
    notify(recipient.id, "message", f"{sender.name}: {preview}",
           link=url_for("messages.thread", user_id=sender.id), replace_unread_link=True)
    db.session.commit()
    return None


@bp.route("/messages")
@login_required
def conversations():
    me = g.user.id
    recent = (Message.query.filter(or_(Message.sender_id == me, Message.recipient_id == me))
              .order_by(Message.created_at.desc(), Message.id.desc()).limit(1000).all())

    threads = {}
    for message in recent:
        other_id = message.recipient_id if message.sender_id == me else message.sender_id
        thread = threads.setdefault(other_id, {"last": message, "unread": 0})
        if message.recipient_id == me and message.read_at is None:
            thread["unread"] += 1

    people = {u.id: u for u in User.query.filter(User.id.in_(threads)).all()} if threads else {}
    rows = [{"user": people[uid], **t} for uid, t in threads.items() if uid in people]
    return render_template("messages/conversations.html", rows=rows,
                           to=request.args.get("to", "")[:254])


@bp.route("/messages/new", methods=["POST"])
@login_required
@limiter.limit("20 per hour", key_func=user_key)
def new_conversation():
    email = clean(request.form, "email", 254).lower()
    body = request.form.get("body") or ""
    recipient = User.query.filter_by(email=email).first() if email else None

    if recipient is None:
        flash("No GAJ account uses that email. Check the spelling, or invite them to GAJ.", "error")
        return redirect(url_for("messages.conversations", to=email))

    error = send_message(g.user, recipient, body)
    if error:
        flash(error, "error")
        return redirect(url_for("messages.conversations", to=email))
    return redirect(url_for("messages.thread", user_id=recipient.id))


def load_thread(other):
    me = g.user.id
    messages = (Message.query.filter(between(me, other.id))
                .order_by(Message.created_at, Message.id).all())[-300:]
    # Opening the conversation reads it
    now = utc_now()
    Message.query.filter_by(sender_id=other.id, recipient_id=me, read_at=None).update({"read_at": now})
    Notification.query.filter_by(user_id=me, read_at=None,
                                 link=url_for("messages.thread", user_id=other.id)
                                 ).update({"read_at": now})
    db.session.commit()
    return messages


def other_user_or_404(user_id):
    """Only people you've already talked to can be opened by id, so ids
    can't be used to look up who has an account."""
    other = db.session.get(User, user_id)
    if other is None or other.id == g.user.id or not have_talked(g.user.id, other.id):
        abort(404)
    return other


@bp.route("/messages/<int:user_id>", methods=["GET", "POST"])
@login_required
@limiter.limit("30 per minute;500 per day", methods=["POST"], key_func=user_key)
def thread(user_id):
    other = other_user_or_404(user_id)

    if request.method == "POST":
        error = send_message(g.user, other, request.form.get("body") or "")
        if error:
            flash(error, "error")
        return redirect(url_for("messages.thread", user_id=other.id) + "#latest")

    i_blocked = Block.query.filter_by(blocker_id=g.user.id, blocked_id=other.id).first() is not None
    return render_template(
        "messages/thread.html", other=other, messages=load_thread(other),
        i_blocked=i_blocked, they_blocked=not i_blocked and blocked_either_way(g.user.id, other.id),
    )


@bp.route("/messages/<int:user_id>/latest")
@login_required
@limiter.exempt
def thread_latest(user_id):
    """Just the message list, fetched every few seconds by the open conversation."""
    other = other_user_or_404(user_id)
    return render_template("messages/_thread.html", other=other, messages=load_thread(other))


@bp.route("/messages/<int:user_id>/block", methods=["POST"])
@login_required
def block(user_id):
    other = other_user_or_404(user_id)
    if not Block.query.filter_by(blocker_id=g.user.id, blocked_id=other.id).first():
        db.session.add(Block(blocker_id=g.user.id, blocked_id=other.id, created_at=utc_now()))
        db.session.commit()
    flash(f"You blocked {other.name}. Neither of you can send messages now.", "success")
    return redirect(url_for("messages.thread", user_id=other.id))


@bp.route("/messages/<int:user_id>/unblock", methods=["POST"])
@login_required
def unblock(user_id):
    other = other_user_or_404(user_id)
    Block.query.filter_by(blocker_id=g.user.id, blocked_id=other.id).delete()
    db.session.commit()
    flash(f"You unblocked {other.name}.", "success")
    return redirect(url_for("messages.thread", user_id=other.id))


@bp.route("/messages/<int:user_id>/report", methods=["POST"])
@login_required
@limiter.limit("10 per day", key_func=user_key)
def report(user_id):
    other = other_user_or_404(user_id)
    reason = clean(request.form, "reason", 1000)
    db.session.add(Report(reporter_id=g.user.id, reported_id=other.id,
                          reason=reason, created_at=utc_now()))
    if not Block.query.filter_by(blocker_id=g.user.id, blocked_id=other.id).first():
        db.session.add(Block(blocker_id=g.user.id, blocked_id=other.id, created_at=utc_now()))
    db.session.commit()

    contact = current_app.config.get("CONTACT_EMAIL")
    if contact:
        send_email(contact, f"GAJ report: user #{other.id}",
                   f"User #{g.user.id} ({g.user.email}) reported user #{other.id} "
                   f"({other.email}).\n\nReason:\n{reason or '(none given)'}\n")

    flash(f"Thanks. We'll review it. {other.name} is blocked and can't message you.", "success")
    return redirect(url_for("messages.conversations"))
