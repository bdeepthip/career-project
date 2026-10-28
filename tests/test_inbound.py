"""
Forwarding addresses: email services post forwarded job emails to
/inbound/email, and they land in the right user's Inbox.
"""

import base64
import json

import pytest

from conftest import add_application, make_app, wipe
from jobtrack.models import JobApplication, JobEmail, User

SECRET = "test-inbound-secret"
DOMAIN = "in.jobtrack.test"


def token_of(app, email="test@example.com"):
    with app.app_context():
        return User.query.filter_by(email=email).one().inbound_token


def address_of(app, email="test@example.com"):
    return f"jt-{token_of(app, email)}@{DOMAIN}"


def status_of(app, company):
    with app.app_context():
        return JobApplication.query.filter_by(company=company).one().status


def email_count(app):
    with app.app_context():
        return JobEmail.query.count()


def postmark(client, to, sender="careers@microsoft.com", subject="Interview invitation",
             text="We'd like to schedule a phone screen.", message_id="<m1@microsoft.com>",
             secret=SECRET, **extra):
    payload = {
        "OriginalRecipient": to, "To": "you@gmail.com", "From": sender,
        "Subject": subject, "TextBody": text,
        "Headers": [{"Name": "Message-ID", "Value": message_id}],
    }
    payload.update(extra)
    return client.post("/inbound/email", json=payload, headers={"X-JobTrack-Secret": secret})


# ---------- Every user gets an address ----------

def test_new_user_gets_a_private_address(app, client, logged_in):
    token = token_of(app)
    assert token and len(token) == 14
    page = client.get("/inbox").data.decode()
    assert f"jt-{token}@{DOMAIN}" in page
    assert "Set up automatic forwarding from Gmail" in page


def test_addresses_are_unique(app, auth):
    auth.register(email="a@example.com")
    auth.register(email="b@example.com")
    assert token_of(app, "a@example.com") != token_of(app, "b@example.com")


def test_new_address_replaces_old_one(app, client, logged_in):
    add_application(client, company="Microsoft")
    old = address_of(app)
    client.post("/inbox/address/new")
    new = address_of(app)
    assert new != old

    assert postmark(client, old).get_json()["status"] == "ignored"
    assert postmark(client, new).get_json()["status"] == "processed"


# ---------- Webhook security ----------

def test_webhook_rejects_wrong_or_missing_secret(app, client, logged_in):
    to = address_of(app)
    assert postmark(client, to, secret="wrong").status_code == 401
    assert client.post("/inbound/email", json={"OriginalRecipient": to}).status_code == 401
    assert email_count(app) == 0


def test_webhook_accepts_secret_in_url_or_basic_auth(app, client, logged_in):
    to = address_of(app)
    payload = {"OriginalRecipient": to, "From": "x@acme.com", "Subject": "Hi", "TextBody": "a"}
    assert client.post(f"/inbound/email?key={SECRET}", json=payload).status_code == 200
    basic = base64.b64encode(f"jobtrack:{SECRET}".encode()).decode()
    payload["TextBody"] = "b"
    response = client.post("/inbound/email", json=payload,
                           headers={"Authorization": f"Basic {basic}"})
    assert response.status_code == 200
    assert email_count(app) == 2


def test_webhook_is_off_without_a_secret(tmp_path):
    app = make_app(tmp_path, INBOUND_WEBHOOK_SECRET="")
    client = app.test_client()
    assert client.post("/inbound/email", json={}, headers={"X-JobTrack-Secret": ""}).status_code == 404
    wipe(app)


def test_inbox_says_when_forwarding_is_off(tmp_path):
    app = make_app(tmp_path, INBOUND_WEBHOOK_SECRET="")
    client = app.test_client()
    client.post("/register", data={"name": "T", "email": "t@example.com", "password": "password123"})
    client.post("/login", data={"email": "t@example.com", "password": "password123"})
    assert b"isn't switched on for this server yet" in client.get("/inbox").data
    wipe(app)


def test_webhook_needs_no_csrf_token_but_address_change_does(tmp_path):
    app = make_app(tmp_path, WTF_CSRF_ENABLED=True)
    client = app.test_client()
    response = client.post("/inbound/email", json={"OriginalRecipient": "jt-x@" + DOMAIN},
                           headers={"X-JobTrack-Secret": SECRET})
    assert response.status_code == 200          # webhook: no CSRF needed
    assert client.post("/inbox/address/new").status_code == 400  # CSRF still required
    wipe(app)


# ---------- Delivery ----------

def test_forwarded_email_updates_the_application(app, client, logged_in):
    add_application(client, company="Microsoft", status="Applied")
    response = postmark(client, address_of(app))
    assert response.get_json()["status"] == "processed"
    assert status_of(app, "Microsoft") == "Interview"
    assert b"Interview invitation" in client.get("/inbox").data


def test_email_goes_only_to_the_addressed_user(app, client, auth):
    auth.register(email="a@example.com")
    auth.register(email="b@example.com")
    postmark(client, address_of(app, "b@example.com"), subject="For B only")

    auth.login(email="a@example.com")
    assert b"For B only" not in client.get("/inbox").data
    auth.logout()
    auth.login(email="b@example.com")
    assert b"For B only" in client.get("/inbox").data


def test_unknown_or_foreign_address_is_ignored(app, client, logged_in):
    token = token_of(app)
    assert postmark(client, f"jt-notarealtoken1@{DOMAIN}").get_json()["status"] == "ignored"
    # right token, wrong domain: not ours
    assert postmark(client, f"jt-{token}@evil.example").get_json()["status"] == "ignored"
    assert email_count(app) == 0


def test_address_is_case_insensitive_and_allows_plus_tags(app, client, logged_in):
    to = address_of(app).upper().replace("@", "+gmail@")
    assert postmark(client, f"Me <{to}>").get_json()["status"] == "processed"


def test_retried_delivery_is_saved_once(app, client, logged_in):
    to = address_of(app)
    assert postmark(client, to).get_json()["status"] == "processed"
    assert postmark(client, to).get_json()["status"] == "duplicate"
    # no Message-ID at all: the content fingerprint still catches the retry
    assert postmark(client, to, message_id="", subject="No id").get_json()["status"] == "processed"
    assert postmark(client, to, message_id="", subject="No id").get_json()["status"] == "duplicate"
    assert email_count(app) == 2


def test_mailgun_form_format(app, client, logged_in):
    add_application(client, company="Stripe")
    response = client.post(f"/inbound/email?key={SECRET}", data={
        "recipient": address_of(app), "from": "Stripe <jobs@stripe.com>",
        "subject": "Update on your application",
        "body-plain": "Unfortunately we will not be moving forward.",
        "Message-Id": "<s1@stripe.com>",
    })
    assert response.get_json()["status"] == "processed"
    assert status_of(app, "Stripe") == "Rejected"


def test_sendgrid_form_format(app, client, logged_in):
    add_application(client, company="Adobe")
    response = client.post(f"/inbound/email?key={SECRET}", data={
        "to": "you@gmail.com", "from": "Adobe <talent@adobe.com>",
        "envelope": json.dumps({"to": [address_of(app)], "from": "talent@adobe.com"}),
        "subject": "Offer", "html": "<p>We are <b>pleased to offer</b> you the role.</p>",
        "headers": "Message-ID: <a1@adobe.com>\nSubject: Offer",
    })
    assert response.get_json()["status"] == "processed"
    assert status_of(app, "Adobe") == "Offer"


def test_raw_email_format(app, client, logged_in):
    add_application(client, company="Intuit")
    raw = (
        "From: Intuit Careers <careers@intuit.com>\r\n"
        "To: you@gmail.com\r\n"
        "Subject: Interview availability\r\n"
        "Message-ID: <i1@intuit.com>\r\n"
        "MIME-Version: 1.0\r\n"
        "Content-Type: multipart/alternative; boundary=XX\r\n\r\n"
        "--XX\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
        "<html><style>p{}</style><p>We would like to schedule an interview.</p></html>\r\n"
        "--XX--\r\n"
    )
    response = client.post("/inbound/email", data=raw.encode(),
                           content_type="message/rfc822",
                           headers={"X-JobTrack-Secret": SECRET, "X-Envelope-To": address_of(app)})
    assert response.get_json()["status"] == "processed"
    assert status_of(app, "Intuit") == "Interview"
    with app.app_context():
        body = JobEmail.query.one().body
    assert "schedule an interview" in body and "<p>" not in body and "p{}" not in body


def test_unreadable_request_is_rejected(app, client):
    response = client.post("/inbound/email", data="x", content_type="application/json",
                           headers={"X-JobTrack-Secret": SECRET})
    assert response.status_code == 400


def test_large_email_with_attachment_is_accepted(app, client, logged_in):
    big = "x" * (3 * 1024 * 1024)  # 3 MB, over the normal 1 MB form limit
    response = postmark(client, address_of(app), Attachments=[{"Content": big}])
    assert response.status_code == 200
    with app.app_context():
        assert len(JobEmail.query.one().body) <= 20000


def test_daily_limit_stops_flooding(tmp_path):
    app = make_app(tmp_path, INBOUND_DAILY_LIMIT=2)
    client = app.test_client()
    client.post("/register", data={"name": "T", "email": "test@example.com", "password": "password123"})
    to = address_of(app)
    for n in range(2):
        assert postmark(client, to, message_id=f"<{n}@x>").get_json()["status"] == "processed"
    assert postmark(client, to, message_id="<3@x>").get_json()["status"] == "ignored"
    wipe(app)


def test_gmail_confirmation_shows_the_code(app, client, logged_in):
    add_application(client, company="Google", status="Interview")
    postmark(client, address_of(app), sender="Gmail Team <forwarding-noreply@google.com>",
             subject="(#123456789) Gmail Forwarding Confirmation - Receive Mail from you@gmail.com",
             text="you@gmail.com has requested to automatically forward mail...\n"
                  "Confirmation code: 123456789\n")
    page = client.get("/inbox").data
    assert b"Gmail forwarding confirmation code: 123456789" in page
    assert b">Setup</span>" in page and b"Choose application" not in page
    assert status_of(app, "Google") == "Interview"  # never treated as a job email


def test_existing_users_get_an_address_from_the_migration(tmp_path):
    """A database from before Phase 4 gains addresses for everyone already in it."""
    import sqlite3
    from flask_migrate import upgrade
    from jobtrack import create_app
    from jobtrack.config import TestConfig

    db_path = tmp_path / "old.db"
    config = type("C", (TestConfig,), {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}"})
    app = create_app(config)
    with app.app_context():
        from jobtrack.db import MIGRATIONS_DIR
        upgrade(directory=MIGRATIONS_DIR, revision="4059315dae7f")  # Phase 3 schema
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO users(name,email,password) VALUES ('A','a@x.com','h'), ('B','b@x.com','h')")
    conn.commit()
    conn.close()

    with app.app_context():
        upgrade(directory=MIGRATIONS_DIR)
        tokens = [u.inbound_token for u in User.query.all()]
    assert len(tokens) == 2 and all(tokens) and tokens[0] != tokens[1]
