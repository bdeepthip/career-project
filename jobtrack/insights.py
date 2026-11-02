"""
Numbers for the dashboard charts: applications per week, the
pipeline, and how often companies write back.

Everything is computed from the user's own applications with two
small queries, so the dashboard stays fast however many there are.
"""

from datetime import date, timedelta

from sqlalchemy import func

from .models import JobApplication, db
from .validation import STATUSES

WEEKS = 8


def week_start(day):
    """Monday of the week that `day` falls in."""
    return day - timedelta(days=day.weekday())


def weekly_counts(user_id, today=None, weeks=WEEKS):
    """[{"start": date, "label": "Oct 26", "count": 3}, ...], oldest
    first, ending with the current week. Weeks with no applications
    are included with a count of 0, so the chart has no gaps."""

    today = today or date.today()
    first = week_start(today) - timedelta(weeks=weeks - 1)

    # date_applied is stored as "YYYY-MM-DD", which sorts as text in
    # date order, so a plain string comparison filters by date.
    rows = (db.session.query(JobApplication.date_applied, func.count())
            .filter(JobApplication.user_id == user_id,
                    JobApplication.date_applied >= first.isoformat())
            .group_by(JobApplication.date_applied))

    buckets = {first + timedelta(weeks=i): 0 for i in range(weeks)}
    for day_text, n in rows:
        try:
            day = date.fromisoformat(day_text)
        except (TypeError, ValueError):
            continue
        start = week_start(day)
        if start in buckets:          # skips dates in the future
            buckets[start] += n

    return [{"start": start, "label": start.strftime("%b %-d"), "count": n}
            for start, n in sorted(buckets.items())]


def chart_bars(weeks, width=560, height=160, gap=10):
    """Turn weekly counts into bar positions for an SVG chart.
    Done here, not in the template, so the template only places
    rectangles. Returns the bars plus the y-axis top value."""

    top = max([w["count"] for w in weeks] + [4])
    # Round the axis up to a tidy number: 4, 8, 12, ...
    top = -(-top // 4) * 4
    bar_width = (width - gap * (len(weeks) - 1)) / len(weeks)

    bars = []
    for i, week in enumerate(weeks):
        bar_height = round(week["count"] / top * height, 1)
        if week["count"]:
            bar_height = max(bar_height, 3)   # a 1 never disappears
        bars.append({
            **week,
            "x": round(i * (bar_width + gap), 1),
            "y": round(height - bar_height, 1),
            "width": round(bar_width, 1),
            "height": bar_height,
            "current": i == len(weeks) - 1,
        })
    return {"bars": bars, "top": top, "width": width, "height": height}


def pipeline(counts):
    """Share of all applications at each status, for the pipeline bars.
    Percentages are whole numbers that a person can check by hand."""

    total = sum(counts.values())
    stages = []
    for status in STATUSES:
        n = counts.get(status, 0)
        stages.append({
            "status": status,
            "count": n,
            "percent": round(n * 100 / total) if total else 0,
        })
    return stages


def rates(counts):
    """Response rate: share of applications that got any answer
    (an interview, an offer or a rejection). Interview rate: share
    that reached an interview or an offer."""

    total = sum(counts.values())
    if not total:
        return {"response": None, "interview": None}
    answered = total - counts.get("Applied", 0)
    interviews = counts.get("Interview", 0) + counts.get("Offer", 0)
    return {
        "response": round(answered * 100 / total),
        "interview": round(interviews * 100 / total),
    }
