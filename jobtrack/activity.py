"""
Screen time: how long each user actively spends on GAJ per day.

The browser pings every 30 seconds while a GAJ tab is visible and the
person has moved, typed or scrolled in the last 3 minutes. Each ping
adds 30 seconds. Pings closer than 25 seconds apart (two open tabs)
count once, so time is never double-counted.
"""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, jsonify, request, session

from .auth import login_required
from .extensions import limiter
from .models import UserActivity, db

bp = Blueprint("activity", __name__)

PING_SECONDS = 30
MIN_GAP = timedelta(seconds=25)
DAILY_GOAL_SECONDS = 7 * 60 * 60
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def local_today():
    """The user's own date (their browser tells us its time-zone offset)."""
    offset = session.get("tz_offset_minutes", 0)
    return (datetime.now(timezone.utc) - timedelta(minutes=offset)).date().isoformat()


def seconds_today(user_id):
    row = UserActivity.query.filter_by(user_id=user_id, day=local_today()).first()
    return row.seconds if row else 0


def format_duration(seconds):
    hours, minutes = divmod(int(seconds) // 60, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


@bp.app_context_processor
def screen_time():
    if not getattr(g, "user", None):
        return {}
    seconds = seconds_today(g.user.id)
    return {
        "screen_seconds": seconds,
        "screen_time": format_duration(seconds),
        "screen_goal_seconds": DAILY_GOAL_SECONDS,
        "screen_percent": min(100, round(seconds * 100 / DAILY_GOAL_SECONDS)),
    }


@bp.route("/activity/ping", methods=["POST"])
@login_required
@limiter.limit("6 per minute")
def ping():
    data = request.get_json(silent=True) or {}
    offset = data.get("tz_offset_minutes")
    if isinstance(offset, int) and -14 * 60 <= offset <= 14 * 60:
        session["tz_offset_minutes"] = offset

    now = datetime.now(timezone.utc)
    day = local_today()
    row = UserActivity.query.filter_by(user_id=g.user.id, day=day).first()
    if row is None:
        row = UserActivity(user_id=g.user.id, day=day, seconds=0)
        db.session.add(row)

    last = (datetime.strptime(row.last_ping, TIME_FORMAT).replace(tzinfo=timezone.utc)
            if row.last_ping else None)
    if last is None or now - last >= MIN_GAP:
        row.seconds = min(row.seconds + PING_SECONDS, 24 * 60 * 60)
        row.last_ping = now.strftime(TIME_FORMAT)
    db.session.commit()

    return jsonify(seconds=row.seconds, display=format_duration(row.seconds),
                   percent=min(100, round(row.seconds * 100 / DAILY_GOAL_SECONDS)))
