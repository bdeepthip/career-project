import pytest

from jobtrack.email_parser import detect_status, match_application, should_update


@pytest.mark.parametrize("subject, body, expected", [
    ("Thank you for applying", "We received your application.", "Applied"),
    ("Interview invitation", "Please share your availability for a phone screen.", "Interview"),
    ("Update", "Unfortunately, we will not be moving forward.", "Rejected"),
    ("Update", "Thank you for your interest. Unfortunately we chose other candidates.", "Rejected"),
    ("Offer", "We are pleased to offer you the position.", "Offer"),
    ("Newsletter", "Our quarterly product update.", None),
])
def test_detect_status(subject, body, expected):
    assert detect_status(subject, body) == expected


@pytest.mark.parametrize("current, new, expected", [
    ("Applied", "Interview", True),
    ("Interview", "Offer", True),
    ("Interview", "Applied", False),   # never backwards
    ("Applied", "Rejected", True),
    ("Offer", "Rejected", False),      # offer is final
    ("Rejected", "Interview", False),
    ("Applied", None, False),
])
def test_should_update(current, new, expected):
    assert should_update(current, new) is expected


def test_match_prefers_sender_and_title():
    apps = [
        {"id": 1, "company": "Amazon", "job_title": "Data Engineer"},
        {"id": 2, "company": "Amazon", "job_title": "Backend Developer"},
        {"id": 3, "company": "Meta", "job_title": "Data Engineer"},
    ]
    best = match_application(apps, "Amazon Jobs <no-reply@amazon.com>",
                             "Your Backend Developer application", "")
    assert best["id"] == 2


def test_match_needs_whole_word():
    apps = [{"id": 1, "company": "Meta", "job_title": "Engineer"}]
    assert match_application(apps, "x@y.com", "Metadata report", "") is None
