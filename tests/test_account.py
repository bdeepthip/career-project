import json
import re

import pytest

from conftest import add_application
from jobtrack import mailer
from jobtrack.db import get_db


@pytest.fixture(autouse=True)
def empty_outbox():
    mailer.outbox.clear()
    yield
    mailer.outbox.clear()


def reset_link_from_email():
    assert len(mailer.outbox) == 1
    body = mailer.outbox[0].get_content()
    return re.search(r"http://localhost(/reset-password/\S+)", body).group(1)


def count_rows(app, table, user_id):
    column = "id" if table == "users" else "user_id"
    with app.app_context():
        return get_db().execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (user_id,)).fetchone()[0]


# ---------- Forgot / reset password ----------

def test_forgot_password_sends_link(client, auth):
    auth.register()
    response = client.post("/forgot-password", data={"email": "TEST@example.com"}, follow_redirects=True)
    assert b"If an account exists" in response.data
    assert mailer.outbox[0]["To"] == "test@example.com"
    assert "/reset-password/" in mailer.outbox[0].get_content()


def test_forgot_password_unknown_email_sends_nothing_but_same_message(client):
    response = client.post("/forgot-password", data={"email": "nobody@example.com"}, follow_redirects=True)
    assert b"If an account exists" in response.data
    assert mailer.outbox == []


def test_reset_password_flow(client, auth):
    auth.register()
    client.post("/forgot-password", data={"email": "test@example.com"})
    link = reset_link_from_email()

    assert client.get(link).status_code == 200
    response = client.post(link, data={"password": "brand-new-pass", "confirm_password": "brand-new-pass"},
                           follow_redirects=True)
    assert b"Your password was reset" in response.data

    assert auth.login(password="password123").status_code == 401
    assert auth.login(password="brand-new-pass").headers["Location"] == "/dashboard"


def test_reset_link_works_only_once(client, auth):
    auth.register()
    client.post("/forgot-password", data={"email": "test@example.com"})
    link = reset_link_from_email()
    client.post(link, data={"password": "first-new-pass", "confirm_password": "first-new-pass"})

    response = client.post(link, data={"password": "second-new-pass", "confirm_password": "second-new-pass"},
                           follow_redirects=True)
    assert b"invalid or has expired" in response.data
    assert auth.login(password="first-new-pass").status_code == 302


def test_expired_reset_link_rejected(app, client, auth):
    auth.register()
    client.post("/forgot-password", data={"email": "test@example.com"})
    link = reset_link_from_email()
    app.config["PASSWORD_RESET_MAX_AGE"] = -1
    response = client.get(link, follow_redirects=True)
    assert b"invalid or has expired" in response.data


def test_tampered_reset_link_rejected(client, auth):
    auth.register()
    client.post("/forgot-password", data={"email": "test@example.com"})
    link = reset_link_from_email()
    response = client.get(link[:-3] + "abc", follow_redirects=True)
    assert b"invalid or has expired" in response.data


def test_reset_requires_matching_passwords(client, auth):
    auth.register()
    client.post("/forgot-password", data={"email": "test@example.com"})
    link = reset_link_from_email()
    response = client.post(link, data={"password": "brand-new-pass", "confirm_password": "different-pass"})
    assert response.status_code == 400
    assert b"don&#39;t match" in response.data


# ---------- Change password / name ----------

def test_change_password(client, logged_in):
    response = client.post("/account/password", follow_redirects=True, data={
        "current_password": "password123", "new_password": "another-pass", "confirm_password": "another-pass"})
    assert b"Password changed" in response.data
    assert client.get("/dashboard").status_code == 200   # this device stays logged in


def test_change_password_wrong_current(client, logged_in):
    response = client.post("/account/password", follow_redirects=True, data={
        "current_password": "wrong", "new_password": "another-pass", "confirm_password": "another-pass"})
    assert b"current password is incorrect" in response.data


def test_password_change_signs_out_other_devices(app, auth):
    auth.register()
    laptop = app.test_client()
    phone = app.test_client()
    for device in (laptop, phone):
        device.post("/login", data={"email": "test@example.com", "password": "password123"})

    laptop.post("/account/password", data={
        "current_password": "password123", "new_password": "another-pass", "confirm_password": "another-pass"})

    assert laptop.get("/dashboard").status_code == 200
    assert phone.get("/dashboard").status_code == 302   # signed out


def test_change_name(client, logged_in):
    client.post("/account/name", data={"name": "New Name"})
    assert b"Welcome, New Name" in client.get("/dashboard").data


# ---------- Export ----------

def test_export_contains_own_data_only(client, auth):
    auth.register(email="other@example.com")
    auth.login(email="other@example.com")
    add_application(client, company="OtherCo")
    auth.logout()

    auth.register()
    auth.login()
    add_application(client, company="MyCo")
    client.post("/skills/add", data={"skill_name": "Python"})

    response = client.get("/account/export")
    assert response.headers["Content-Disposition"].startswith("attachment;")
    data = json.loads(response.data)

    assert data["account"] == {"name": "Test User", "email": "test@example.com"}
    assert [a["company"] for a in data["applications"]] == ["MyCo"]
    assert data["skills"] == ["Python"]
    assert b"OtherCo" not in response.data
    assert b"pbkdf2" not in response.data and b"scrypt" not in response.data   # no password hash


# ---------- Delete account ----------

def test_delete_account_wrong_password_keeps_everything(app, client, logged_in):
    add_application(client)
    response = client.post("/account/delete", data={"password": "wrong"}, follow_redirects=True)
    assert b"Your account was not deleted" in response.data
    assert count_rows(app, "users", 1) == 1


def test_delete_account_removes_all_data(app, client, auth):
    # Another user whose data must survive
    auth.register(email="keep@example.com")
    auth.login(email="keep@example.com")
    add_application(client, company="KeepCo")
    auth.logout()

    auth.register()
    auth.login()
    add_application(client, company="Microsoft")
    client.post("/skills/add", data={"skill_name": "Python"})
    client.post("/education/add", data={"institution": "Temple", "degree": "MS",
                                        "field_of_study": "", "start_year": "", "end_year": ""})
    client.post("/experience/add", data={"company": "Accenture", "job_title": "Associate", "location": "",
                                         "start_date": "", "end_date": "", "description": ""})
    client.post("/profile", data={"headline": "x", "phone": "", "location": "", "domain": "",
                                  "target_role": "", "experience_level": "", "preferred_location": "", "about": ""})
    client.post("/inbox/add", data={"sender": "careers@microsoft.com", "subject": "Interview", "body": "interview"})

    response = client.post("/account/delete", data={"password": "password123"}, follow_redirects=True)
    assert b"permanently deleted" in response.data

    for table in ["users", "job_applications", "skills", "education", "experience", "profiles", "job_emails"]:
        assert count_rows(app, table, 2) == 0, table

    assert client.get("/dashboard").status_code == 302
    assert auth.login().status_code == 401

    auth.login(email="keep@example.com")
    assert b"KeepCo" in client.get("/dashboard").data


def test_account_pages_require_login(client):
    assert client.get("/account").status_code == 302
    assert client.get("/account/export").status_code == 302
    assert client.post("/account/delete", data={"password": "x"}).status_code == 302
