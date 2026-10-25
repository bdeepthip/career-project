"""
Server-side checks for form input.

The browser's `required` and `type="url"` checks are easy to skip
(anyone can send a request without using the form), so the server
checks everything again before saving.
"""

import re
from datetime import date
from urllib.parse import urlparse

STATUSES = ["Applied", "Interview", "Offer", "Rejected"]

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MIN_PASSWORD_LENGTH = 8


def clean(form, field, max_length=500):
    """Get a form field as trimmed text, capped at max_length."""
    return (form.get(field) or "").strip()[:max_length]


def is_valid_email(email):
    return bool(EMAIL_PATTERN.match(email)) and len(email) <= 254


def is_safe_url(url):
    """Only allow http(s) links. Blocks javascript: links, which would
    run code when someone clicks "View Job"."""
    if not url:
        return True
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def is_valid_date(value):
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def validate_application(form):
    """Return (data, errors) for the add/edit application form."""

    data = {
        "company": clean(form, "company", 120),
        "job_title": clean(form, "job_title", 120),
        "location": clean(form, "location", 120),
        "job_url": clean(form, "job_url", 1000),
        "date_applied": clean(form, "date_applied", 10),
        "status": clean(form, "status", 20),
        "notes": clean(form, "notes", 5000),
    }

    errors = []
    if not data["company"]:
        errors.append("Company is required.")
    if not data["job_title"]:
        errors.append("Job title is required.")
    if not is_valid_date(data["date_applied"]):
        errors.append("Enter a valid date applied.")
    if data["status"] not in STATUSES:
        errors.append("Choose a valid status.")
    if not is_safe_url(data["job_url"]):
        errors.append("Job URL must start with http:// or https://.")

    return data, errors
