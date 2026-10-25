"""
Reads a job-related email and works out two things:

1. What it means  -> Applied, Interview, Offer, Rejected, or None
2. Which application it belongs to -> matched by company name

This is rule-based (keyword phrases), not AI. It is fast, free,
and easy to explain, but it can miss unusual wording. That is why
the Inbox page lets you correct the match by hand.
"""

import re


# ============================================================
# STATUS DETECTION
# ============================================================

# Checked in this order. Rejected and Offer come before Interview
# because rejection emails often mention "interview" too
# ("thank you for taking the time to interview...").
STATUS_PHRASES = [
    ("Offer", [
        "pleased to offer",
        "pleased to extend",
        "extend an offer",
        "extend you an offer",
        "offer letter",
        "offer of employment",
        "job offer",
    ]),
    ("Rejected", [
        "unfortunately",
        "not moving forward",
        "not be moving forward",
        "move forward with other candidates",
        "decided to pursue other candidates",
        "pursue other candidates",
        "not been selected",
        "were not selected",
        "regret to inform",
        "position has been filled",
        "no longer under consideration",
        "will not be proceeding",
    ]),
    ("Interview", [
        "interview",
        "phone screen",
        "schedule a call",
        "schedule time",
        "your availability",
        "next round",
        "online assessment",
        "coding challenge",
        "technical assessment",
        "hackerrank",
        "codesignal",
    ]),
    ("Applied", [
        "thank you for applying",
        "thanks for applying",
        "application received",
        "received your application",
        "application has been received",
        "application has been submitted",
        "successfully submitted",
        "thank you for your application",
        "thank you for your interest",
    ]),
]


def detect_status(subject, body):
    """Return 'Applied', 'Interview', 'Offer', 'Rejected', or None."""

    text = f"{subject or ''} {body or ''}".lower()

    for status, phrases in STATUS_PHRASES:
        for phrase in phrases:
            if phrase in text:
                return status

    return None


# ============================================================
# STATUS RULES (never move an application backwards)
# ============================================================

STATUS_RANK = {"Applied": 1, "Interview": 2, "Offer": 3}


def should_update(current_status, new_status):
    """Decide if an email is allowed to change an application.

    - Moving forward (Applied -> Interview -> Offer) is allowed.
    - Rejected can happen at any stage, except after an Offer.
    - Going backwards (Interview -> Applied) is never allowed,
      e.g. a late "thanks for applying" email won't undo progress.
    """

    if not new_status or new_status == current_status:
        return False

    if current_status in ("Rejected", "Offer"):
        return False

    if new_status == "Rejected":
        return True

    return STATUS_RANK.get(new_status, 0) > STATUS_RANK.get(current_status, 0)


# ============================================================
# MATCHING AN EMAIL TO AN APPLICATION
# ============================================================

def _contains_word(text, phrase):
    """True if phrase appears in text as whole words.
    'Meta' matches 'Meta Platforms' but not 'metadata'."""

    pattern = r"(?<![a-z0-9])" + re.escape(phrase.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def match_application(applications, sender, subject, body):
    """Pick the application this email is most likely about.

    Scores each application by where its company name appears:
    sender (+3), subject (+2), body (+1). If the job title also
    appears, +2 more (helps when you applied to two roles at one
    company). Returns the best application, or None if no
    company name was found anywhere.
    """

    sender_l = (sender or "").lower()
    subject_l = (subject or "").lower()
    body_l = (body or "").lower()

    best = None
    best_score = 0

    for app in applications:
        company = (app["company"] or "").strip()
        if not company:
            continue

        score = 0

        if _contains_word(sender_l, company):
            score += 3
        if _contains_word(subject_l, company):
            score += 2
        if _contains_word(body_l, company):
            score += 1

        if score == 0:
            continue

        title = (app["job_title"] or "").strip()
        if title and (
            _contains_word(subject_l, title) or _contains_word(body_l, title)
        ):
            score += 2

        if score > best_score:
            best = app
            best_score = score

    return best
