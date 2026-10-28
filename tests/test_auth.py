from flask import session


def test_register_then_login(client, auth):
    response = auth.register()
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"

    response = auth.login()
    assert response.headers["Location"] == "/dashboard"

    with client:
        client.get("/dashboard")
        assert session["user_id"] == 1


def test_register_rejects_duplicate_email_any_case(auth):
    auth.register(email="test@example.com")
    response = auth.register(email="TEST@example.com")
    assert response.status_code == 400
    assert b"already exists" in response.data


def test_register_rejects_short_password(auth):
    response = auth.register(password="short")
    assert response.status_code == 400
    assert b"at least 8 characters" in response.data


def test_register_rejects_bad_email(auth):
    response = auth.register(email="not-an-email")
    assert response.status_code == 400


def test_password_is_hashed(app, auth):
    auth.register(password="password123")
    from jobtrack.models import User
    with app.app_context():
        stored = User.query.one().password
    assert stored != "password123"


def test_wrong_password_shows_generic_message(auth):
    auth.register()
    response = auth.login(password="wrong-password")
    assert response.status_code == 401
    assert b"Incorrect email or password" in response.data


def test_unknown_email_shows_same_message(auth):
    response = auth.login(email="nobody@example.com")
    assert b"Incorrect email or password" in response.data


def test_logout_clears_session(client, logged_in):
    logged_in.logout()
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_logout_requires_post(client, logged_in):
    assert client.get("/logout").status_code == 405


def test_pages_require_login(client):
    for path in ["/dashboard", "/applications/add", "/profile", "/jobs", "/match", "/inbox"]:
        response = client.get(path)
        assert response.status_code == 302, path
        assert "/login" in response.headers["Location"], path


def test_login_redirects_back_to_requested_page(client, auth):
    auth.register()
    response = client.post("/login?next=/profile",
                           data={"email": "test@example.com", "password": "password123"})
    assert response.headers["Location"] == "/profile"


def test_login_blocks_offsite_redirect(client, auth):
    auth.register()
    for target in ["https://evil.example", "//evil.example", "javascript:alert(1)"]:
        client.post("/logout")
        response = client.post(f"/login?next={target}",
                               data={"email": "test@example.com", "password": "password123"})
        assert response.headers["Location"] == "/dashboard", target
