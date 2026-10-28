from conftest import add_application


def paste(client, sender, subject, body):
    return client.post("/inbox/add", data={"sender": sender, "subject": subject, "body": body},
                       follow_redirects=True)


def status_of(app, company):
    from jobtrack.models import JobApplication
    with app.app_context():
        return JobApplication.query.filter_by(company=company).one().status


def test_interview_email_updates_status(app, client, logged_in):
    add_application(client, company="Microsoft", status="Applied")
    response = paste(client, "careers@microsoft.com", "Interview invitation",
                     "We'd like to schedule a phone screen.")
    assert b"Status changed: Applied -&gt; Interview" in response.data
    assert status_of(app, "Microsoft") == "Interview"


def test_late_confirmation_does_not_go_backwards(app, client, logged_in):
    add_application(client, company="Amazon", status="Interview")
    paste(client, "no-reply@amazon.com", "Thank you for applying", "We received your application.")
    assert status_of(app, "Amazon") == "Interview"


def test_unmatched_email_then_manual_link(app, client, logged_in):
    add_application(client, company="Stripe Inc", status="Applied")
    response = paste(client, "talent@greenhouse.io", "Next steps", "We'd like to interview you.")
    assert b"No matching application found" in response.data

    response = client.post("/inbox/1/assign", data={"application_id": 1}, follow_redirects=True)
    assert b"Status changed" in response.data
    assert status_of(app, "Stripe Inc") == "Interview"


def test_inbox_is_private(client, auth):
    auth.register(email="a@example.com")
    auth.login(email="a@example.com")
    add_application(client, company="Microsoft")
    paste(client, "careers@microsoft.com", "Private subject", "Interview")
    auth.logout()

    auth.register(email="b@example.com")
    auth.login(email="b@example.com")
    assert b"Private subject" not in client.get("/inbox").data
    assert client.post("/inbox/1/assign", data={"application_id": 1}).status_code == 404
    client.post("/inbox/1/delete")
    auth.logout()

    auth.login(email="a@example.com")
    assert b"Private subject" in client.get("/inbox").data


def test_gmail_sync_blocked_for_other_users(client, logged_in, monkeypatch):
    monkeypatch.setenv("EMAIL_ADDRESS", "owner@gmail.com")
    monkeypatch.setenv("EMAIL_APP_PASSWORD", "x")
    assert b"Sync now" not in client.get("/inbox").data
    assert client.post("/inbox/sync").status_code == 403


def test_gmail_sync_for_owner(client, auth, monkeypatch):
    monkeypatch.setenv("EMAIL_ADDRESS", "owner@gmail.com")
    monkeypatch.setenv("EMAIL_APP_PASSWORD", "x")
    monkeypatch.setattr("jobtrack.inbox.fetch_job_emails", lambda: [
        {"message_id": "<1@x>", "sender": "Meta <jobs@meta.com>", "subject": "Update",
         "body": "Unfortunately we will not be moving forward.", "received_at": "2026-10-22 10:00"},
    ] * 2)
    auth.register(email="owner@gmail.com")
    auth.login(email="owner@gmail.com")
    add_application(client, company="Meta", status="Interview")

    response = client.post("/inbox/sync", follow_redirects=True)
    assert b"1 new email(s), 1 application(s) updated" in response.data
    response = client.post("/inbox/sync", follow_redirects=True)
    assert b"0 new email(s)" in response.data
