"""Friendly dates: 'today', '3 days ago', 'Oct 2'."""

from datetime import date, datetime


def _parse(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    return None


def month_label(value):
    """'2022-08' -> 'Aug 2022' (experience dates come from a month picker)."""
    try:
        return datetime.strptime((value or "")[:7], "%Y-%m").strftime("%b %Y")
    except ValueError:
        return value or ""


def time_ago(value, now=None):
    when = _parse(value)
    if when is None:
        return value or ""
    now = now or datetime.now()
    has_time = len(value.strip()) > 10
    if has_time:
        minutes = int((now - when).total_seconds() // 60)
        if minutes < 1:
            return "just now"
        if minutes < 60:
            return f"{minutes} min ago"
        if minutes < 24 * 60:
            hours = minutes // 60
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = (now.date() - when.date()).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    return when.strftime("%b %-d, %Y") if when.year != now.year else when.strftime("%b %-d")
