"""
Messages between users, blocking, reporting, and notifications.
"""

import pytest

from conftest import add_application, make_app, wipe
from jobtrack import mailer
from jobtrack.models import Message, Notification, User, db

A, B, C = "a@example.com", "b@example.com", "c@example.com"


def user_id(app, email):
    with app.app_context():
        return User.query.filter_by(email=email).one().id


def as_user(auth, email):
    auth.logout()
    auth.login(email=email)


@pytest.fixture
def three(auth):
    for email, name in ((A, "Asha Rao"), (B, "Ben Ortiz"), (C, "Cara Lee")):
        auth.register(name=name, email=email)
    auth.login(email=A)
    return auth


def say(client, to_email, body):
    return client.post("/messages/new", data={"email": to_email, "body": body})


# ---------- Sending ----------

def test_message_someone_by_email(app, client, three):
    response = say(client, B, "Want to swap resume feedback?")
    assert response.headers["Location"].endswith(f"/messages/{user_id(app, B)}")
    as_user(three, B)
    page = client.get("/messages").get_data(as_text=True)
    assert "Asha Rao" in page and "Want to swap resume feedback?" in page


def test_unknown_email_and_self_are_refused(app, client, three):
    response = client.post("/messages/new", data={"email": "nobody@example.com", "body": "hi"},
                           follow_redirects=True)
    assert b"No GAJ account uses that email" in response.data
    say(client, A, "talking to myself")
    with app.app_context():
        assert Message.query.count() == 0


def test_reply_and_read_receipts(app, client, three):
    say(client, B, "Hello Ben")
    as_user(three, B)
    a_id = user_id(app, A)
    assert b">1<span class=\"sr-only\"> unread" in client.get("/dashboard").data   # sidebar badge
    client.get(f"/messages/{a_id}")                                                # reading clears it
    assert b"> unread</span>" not in client.get("/dashboard").data
    client.post(f"/messages/{a_id}", data={"body": "Hi Asha!"})
    as_user(three, A)
    page = client.get(f"/messages/{user_id(app, B)}").get_data(as_text=True)
    assert "Hi Asha!" in page and "Hello Ben" in page


def test_strangers_cannot_open_a_thread_by_id(app, client, three):
    say(client, B, "private")
    as_user(three, C)
    assert client.get(f"/messages/{user_id(app, B)}").status_code == 404
    assert client.get(f"/messages/{user_id(app, A)}").status_code == 404
    assert client.post(f"/messages/{user_id(app, A)}", data={"body": "x"}).status_code == 404


def test_messages_are_private(app, client, three):
    say(client, B, "secret plan")
    as_user(three, C)
    assert b"secret plan" not in client.get("/messages").data


def test_message_text_is_escaped(app, client, three):
    say(client, B, "<script>alert(1)</script>")
    page = client.get(f"/messages/{user_id(app, B)}").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


def test_live_update_fragment(app, client, three):
    say(client, B, "first")
    fragment = client.get(f"/messages/{user_id(app, B)}/latest").get_data(as_text=True)
    assert "first" in fragment and "<html" not in fragment and 'data-count="1"' in fragment


# ---------- Blocking and reporting ----------

def test_block_stops_messages_both_ways(app, client, three):
    say(client, B, "hi")
    b_id, a_id = user_id(app, B), user_id(app, A)
    client.post(f"/messages/{b_id}/block")
    client.post(f"/messages/{b_id}", data={"body": "after block"})
    as_user(three, B)
    client.post(f"/messages/{a_id}", data={"body": "can you see this?"})
    with app.app_context():
        assert Message.query.count() == 1
    assert b"You can't reply" in client.get(f"/messages/{a_id}").data


def test_unblock(app, client, three):
    say(client, B, "hi")
    b_id = user_id(app, B)
    client.post(f"/messages/{b_id}/block")
    client.post(f"/messages/{b_id}/unblock")
    client.post(f"/messages/{b_id}", data={"body": "back again"})
    with app.app_context():
        assert Message.query.count() == 2


def test_report_emails_the_team_and_blocks(app, client, three):
    as_user(three, B)
    say(client, A, "buy my crypto course")
    as_user(three, A)
    mailer.outbox.clear()
    b_id = user_id(app, B)
    client.post(f"/messages/{b_id}/report", data={"reason": "spam"})
    assert mailer.outbox[0]["To"] == "hello@jobtrack.test"
    assert "spam" in mailer.outbox[0].get_content()
    assert b"Unblock Ben" in client.get(f"/messages/{b_id}").data
    mailer.outbox.clear()


# ---------- Notifications ----------

def test_message_notification_and_grouping(app, client, three):
    say(client, B, "one")
    client.post(f"/messages/{user_id(app, B)}", data={"body": "two"})
    with app.app_context():
        notes = Notification.query.filter_by(user_id=user_id(app, B)).all()
    assert len(notes) == 1 and notes[0].text == "Asha Rao: two"   # grouped, latest text


def test_open_notification_marks_read_and_goes_to_link(app, client, three):
    say(client, B, "ping")
    as_user(three, B)
    with app.app_context():
        note_id = Notification.query.one().id
    response = client.post(f"/notifications/{note_id}/open")
    assert response.headers["Location"].endswith(f"/messages/{user_id(app, A)}")
    with app.app_context():
        assert Notification.query.one().read_at is not None


def test_mark_all_read(app, client, three):
    say(client, B, "x")
    as_user(three, B)
    assert b"Mark all as read" in client.get("/notifications").data
    client.post("/notifications/read-all")
    assert b"You're all caught up" not in client.get("/notifications").data
    assert b"Mark all as read" not in client.get("/notifications").data


def test_cannot_open_someone_elses_notification(app, client, three):
    say(client, B, "x")
    with app.app_context():
        note_id = Notification.query.one().id
    assert client.post(f"/notifications/{note_id}/open").status_code == 404


def test_forwarded_email_status_change_notifies(app, client, logged_in):
    add_application(client, company="Adobe", job_title="Data Engineer", status="Applied")
    with app.app_context():
        token = User.query.one().inbound_token
    client.post("/inbound/email", headers={"X-JobTrack-Secret": "test-inbound-secret"}, json={
        "OriginalRecipient": f"gaj-{token}@in.jobtrack.test", "From": "talent@adobe.com",
        "Subject": "Interview invitation", "TextBody": "We'd like to schedule an interview.",
    })
    page = client.get("/notifications").get_data(as_text=True)
    assert "Interview with Adobe: your Data Engineer application is now Interview." in page


def test_pasted_email_does_not_notify(app, client, logged_in):
    add_application(client, company="Adobe", status="Applied")
    client.post("/inbox/add", data={"sender": "talent@adobe.com", "subject": "Interview",
                                    "body": "We'd like to schedule an interview."})
    with app.app_context():
        assert Notification.query.count() == 0   # you were watching; no need


def test_reaching_seven_hours_notifies_once(app, client, logged_in):
    from datetime import datetime, timezone
    from jobtrack.models import UserActivity
    with app.app_context():
        db.session.add(UserActivity(user_id=User.query.one().id,
                                    day=datetime.now(timezone.utc).date().isoformat(),
                                    seconds=7 * 3600 - 10))
        db.session.commit()
    client.post("/activity/ping", json={"tz_offset_minutes": 0})
    with app.app_context():
        assert Notification.query.filter_by(kind="goal").count() == 1


# ---------- Account deletion and export ----------

def test_deleting_an_account_removes_its_conversations(app, client, three):
    say(client, B, "hello")
    as_user(three, B)
    client.post(f"/messages/{user_id(app, A)}", data={"body": "hi back"})
    client.post("/account/delete", data={"password": "password123"})
    with app.app_context():
        assert Message.query.count() == 0
        assert Notification.query.count() == 0


def test_export_includes_messages(app, client, three):
    say(client, B, "exported?")
    data = client.get("/account/export").get_json()
    assert data["messages"][0]["body"] == "exported?" and data["messages"][0]["from"] == "me"


# ---------- Rate limits keyed by account (regression) ----------

def test_logged_in_rate_limits_work_with_limits_on(tmp_path):
    app = make_app(tmp_path, RATELIMIT_ENABLED=True)
    client = app.test_client()
    for email in (A, B):
        client.post("/register", data={"name": "X Y", "email": email, "password": "password123"})
    client.post("/login", data={"email": A, "password": "password123"})
    statuses = [client.post("/messages/new", data={"email": B, "body": f"m{i}"}).status_code
                for i in range(21)]
    assert statuses[:20] == [302] * 20 and statuses[20] == 429
    wipe(app)
