"""
Launch readiness: production safety checks, HTTPS behind a proxy,
security headers, rate limits, health check, legal pages, beta invites.
"""

import pytest

from conftest import make_app, wipe
from jobtrack import create_app, mailer
from jobtrack.config import ProductionConfig, check_production_settings

GOOD_PRODUCTION = {
    "SECRET_KEY": "x" * 64,
    "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://u:p@db.example.com/jobtrack",
    "MAIL_SERVER": "smtp.resend.com",
}


# ---------- Production refuses unsafe settings ----------

def test_production_refuses_unsafe_settings():
    problems = check_production_settings({
        "SECRET_KEY": "short",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///database.db",
        "MAIL_SERVER": "",
    })
    joined = " ".join(problems)
    assert "SECRET_KEY" in joined and "PostgreSQL" in joined and "MAIL_SERVER" in joined


def test_production_accepts_good_settings():
    assert check_production_settings(GOOD_PRODUCTION) == []


def test_production_app_will_not_start_on_sqlite():
    config = type("P", (ProductionConfig,), {**GOOD_PRODUCTION,
                                             "SQLALCHEMY_DATABASE_URI": "sqlite:///x.db"})
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        create_app(config)


def production_app(tmp_path, monkeypatch):
    """A production-mode app (HTTPS, proxy, headers) on a SQLite test database."""
    import jobtrack
    monkeypatch.setattr(jobtrack, "check_production_settings", lambda config: [])
    config = type("P", (ProductionConfig,), {
        **GOOD_PRODUCTION, "TESTING": True, "WTF_CSRF_ENABLED": False,
        "RATELIMIT_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'prod.db'}",
    })
    app = create_app(config)
    with app.app_context():
        from jobtrack.db import init_db
        init_db()
    return app


def test_reset_links_use_https_behind_the_hosts_proxy(tmp_path, monkeypatch):
    app = production_app(tmp_path, monkeypatch)
    client = app.test_client()
    https = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": "jobtrack.app"}
    client.post("/register", data={"name": "T", "email": "t@example.com",
                                   "password": "password123"}, headers=https)
    mailer.outbox.clear()
    client.post("/forgot-password", data={"email": "t@example.com"}, headers=https)
    assert "https://jobtrack.app/reset-password/" in mailer.outbox[0].get_content()
    mailer.outbox.clear()


def test_production_sends_hsts_and_secure_cookie(tmp_path, monkeypatch):
    app = production_app(tmp_path, monkeypatch)
    client = app.test_client()
    response = client.post("/login", data={"email": "a@b.com", "password": "x"},
                           headers={"X-Forwarded-Proto": "https"})
    assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
    assert app.config["SESSION_COOKIE_SECURE"] is True


# ---------- Headers and health ----------

def test_content_security_policy_blocks_inline_scripts(client):
    csp = client.get("/login").headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp
    assert "frame-ancestors 'none'" in csp


def test_no_inline_javascript_in_templates():
    """Inline <script> or onclick= would be blocked by the policy above."""
    import pathlib, re
    templates = pathlib.Path(__file__).parent.parent / "jobtrack" / "templates"
    for path in templates.rglob("*.html"):
        html = path.read_text()
        assert not re.search(r"<script(?![^>]*\bsrc=)", html), path
        assert not re.search(r"\son[a-z]+=", html), path


def test_development_has_no_hsts(client):
    assert "Strict-Transport-Security" not in client.get("/login").headers


def test_health_check(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


# ---------- Rate limits ----------

@pytest.fixture
def limited_client(tmp_path):
    app = make_app(tmp_path, RATELIMIT_ENABLED=True)
    yield app.test_client()
    wipe(app)


def test_password_guessing_on_one_account_is_stopped(limited_client):
    for _ in range(10):
        assert limited_client.post("/login", data={"email": "victim@example.com",
                                                   "password": "guess"}).status_code == 401
    response = limited_client.post("/login", data={"email": "victim@example.com",
                                                   "password": "guess"})
    assert response.status_code == 429
    assert b"Too many attempts" in response.data
    # other people on the same network can still log in
    assert limited_client.post("/login", data={"email": "someone@example.com",
                                               "password": "x"}).status_code == 401


def test_reset_emails_to_one_address_are_limited(limited_client):
    for _ in range(3):
        assert limited_client.post("/forgot-password",
                                   data={"email": "a@example.com"}).status_code == 302
    assert limited_client.post("/forgot-password",
                               data={"email": "a@example.com"}).status_code == 429


def test_viewing_pages_is_not_limited(limited_client):
    for _ in range(40):
        assert limited_client.get("/login").status_code == 200


# ---------- Legal pages ----------

def test_privacy_and_terms_are_public_and_linked(client):
    for path, heading in (("/privacy", b"Privacy Policy"), ("/terms", b"Terms of Use")):
        response = client.get(path)
        assert response.status_code == 200 and heading in response.data
        assert b"hello@jobtrack.test" in response.data
    register = client.get("/register").data
    assert b'href="/terms"' in register and b'href="/privacy"' in register


def test_footer_shows_feedback_link_when_set(tmp_path):
    app = make_app(tmp_path, FEEDBACK_URL="https://forms.example.com/jobtrack")
    assert b"https://forms.example.com/jobtrack" in app.test_client().get("/login").data
    wipe(app)


# ---------- Private beta ----------

@pytest.fixture
def beta_client(tmp_path):
    app = make_app(tmp_path, BETA_INVITE_CODE="Temple-Beta")
    yield app.test_client()
    wipe(app)


def test_beta_sign_up_needs_the_invite_code(beta_client):
    assert b'name="invite_code"' in beta_client.get("/register").data
    response = beta_client.post("/register", data={
        "name": "T", "email": "t@example.com", "password": "password123", "invite_code": "wrong"})
    assert response.status_code == 400 and b"private beta" in response.data
    response = beta_client.post("/register", data={
        "name": "T", "email": "t@example.com", "password": "password123",
        "invite_code": " temple-beta "})
    assert response.status_code == 302


def test_open_sign_up_without_invite_code(client):
    assert b'name="invite_code"' not in client.get("/register").data
