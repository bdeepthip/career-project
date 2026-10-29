"""
Phone numbers: verify in Account, then log in with a text-message code.
"""

import re
from datetime import datetime, timedelta, timezone

import pytest

from conftest import make_app, wipe
from jobtrack import sms
from jobtrack.models import PhoneCode, User, db

PHONE = "(215) 555-0123"
E164 = "+12155550123"


@pytest.fixture(autouse=True)
def empty_outbox():
    sms.outbox.clear()
    yield
    sms.outbox.clear()


def last_code():
    return re.search(r"\b(\d{6})\b", sms.outbox[-1][1]).group(1)


def link_phone(client, phone=PHONE):
    client.post("/account/phone", data={"phone": phone})
    return client.post("/account/phone/verify", data={"code": last_code()}, follow_redirects=True)


# ---------- Numbers ----------

@pytest.mark.parametrize("raw", ["(215) 555-0123", "215.555.0123", "+1 215 555 0123", "12155550123"])
def test_normalize_us_numbers(raw):
    assert sms.normalize_phone(raw) == E164


@pytest.mark.parametrize("raw", ["555-0123", "+44 20 7946 0958", "(015) 555-0123", "(215) 155-0123", "", "abc"])
def test_reject_non_us_or_invalid_numbers(raw):
    assert sms.normalize_phone(raw) is None


def test_display_and_mask():
    assert sms.display_phone(E164) == "(215) 555-0123"
    assert sms.masked_phone(E164).endswith("0123") and "215" not in sms.masked_phone(E164)


# ---------- Adding a number ----------

def test_add_and_verify_phone(app, client, logged_in):
    page = link_phone(client).get_data(as_text=True)
    assert "(215) 555-0123 is verified" in page
    assert sms.outbox[0][0] == E164
    with app.app_context():
        assert User.query.one().phone == E164


def test_wrong_code_does_not_link(app, client, logged_in):
    client.post("/account/phone", data={"phone": PHONE})
    assert client.post("/account/phone/verify", data={"code": "000000"}).status_code == 400
    with app.app_context():
        assert User.query.one().phone is None


def test_number_can_only_belong_to_one_account(client, auth):
    auth.register(email="a@example.com"); auth.login(email="a@example.com")
    link_phone(client); auth.logout()
    auth.register(email="b@example.com"); auth.login(email="b@example.com")
    page = client.post("/account/phone", data={"phone": PHONE}, follow_redirects=True).data
    assert b"already linked to another GAJ account" in page
    assert len(sms.outbox) == 1   # no text sent for the second account


def test_remove_phone(app, client, logged_in):
    link_phone(client)
    client.post("/account/phone/remove")
    with app.app_context():
        assert User.query.one().phone is None


# ---------- Logging in ----------

def test_log_in_with_a_text_code(client, logged_in):
    link_phone(client)
    logged_in.logout()
    sms.outbox.clear()

    response = client.post("/login/phone", data={"phone": "215-555-0123"}, follow_redirects=True)
    assert b"we just texted it a 6-digit code" in response.data
    response = client.post("/login/phone/code", data={"code": last_code()})
    assert response.status_code == 302 and response.headers["Location"].endswith("/dashboard")
    assert client.get("/dashboard").status_code == 200


def test_code_works_only_once(client, logged_in):
    link_phone(client)
    logged_in.logout()
    client.post("/login/phone", data={"phone": PHONE})
    code = last_code()
    client.post("/login/phone/code", data={"code": code})
    logged_in.logout()
    client.post("/login/phone", data={"phone": PHONE})
    sms.outbox.append((E164, f"old code {code}"))  # try the used code again
    assert client.post("/login/phone/code", data={"code": code}).status_code == 401


def test_unknown_number_gets_same_message_and_no_text(client):
    response = client.post("/login/phone", data={"phone": "(267) 555-0199"}, follow_redirects=True)
    assert b"we just texted it a 6-digit code" in response.data
    assert sms.outbox == []   # nothing texted to a stranger
    assert client.post("/login/phone/code", data={"code": "123456"}).status_code == 401


def test_expired_code_fails(app, client, logged_in):
    link_phone(client)
    logged_in.logout()
    client.post("/login/phone", data={"phone": PHONE})
    with app.app_context():
        row = PhoneCode.query.one()
        row.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
        db.session.commit()
    assert client.post("/login/phone/code", data={"code": last_code()}).status_code == 401


def test_five_wrong_guesses_burn_the_code(client, logged_in):
    link_phone(client)
    logged_in.logout()
    client.post("/login/phone", data={"phone": PHONE})
    code = last_code()
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        client.post("/login/phone/code", data={"code": wrong})
    assert client.post("/login/phone/code", data={"code": code}).status_code == 401


def test_code_page_without_a_number_goes_back(client):
    response = client.get("/login/phone/code")
    assert response.status_code == 302 and response.headers["Location"].endswith("/login/phone")


def test_login_page_offers_email_and_phone(client):
    page = client.get("/login").data
    assert b">Email</a>" in page and b">Phone</a>" in page


# ---------- Limits and production ----------

def test_texts_to_one_number_are_limited(tmp_path):
    app = make_app(tmp_path, RATELIMIT_ENABLED=True)
    client = app.test_client()
    for _ in range(3):
        assert client.post("/login/phone", data={"phone": PHONE}).status_code == 302
    assert client.post("/login/phone", data={"phone": PHONE}).status_code == 429
    wipe(app)


def test_phone_login_off_in_production_without_twilio(tmp_path, monkeypatch):
    import jobtrack
    monkeypatch.setattr(jobtrack, "check_production_settings", lambda c: [])
    app = make_app(tmp_path, PRODUCTION=True)
    client = app.test_client()
    assert client.get("/login/phone").status_code == 404
    assert b">Phone</a>" not in client.get("/login").data
    wipe(app)


def test_twilio_is_used_when_configured(tmp_path, monkeypatch):
    calls = []

    def fake_twilio(path, fields):
        calls.append((path, fields))
        return {"status": "approved"} if path == "VerificationCheck" else {"status": "pending"}

    monkeypatch.setattr(sms, "_twilio", fake_twilio)
    app = make_app(tmp_path, TWILIO_ACCOUNT_SID="AC1", TWILIO_AUTH_TOKEN="t",
                   TWILIO_VERIFY_SERVICE_SID="VA1")
    with app.test_request_context():
        sms.send_code(E164)
        assert sms.check_code(E164, "123456") is True
    assert calls == [("Verifications", {"To": E164, "Channel": "sms"}),
                     ("VerificationCheck", {"To": E164, "Code": "123456"})]
    assert sms.outbox == []   # Twilio sent it, not GAJ
    wipe(app)
