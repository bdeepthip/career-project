import pytest

from conftest import add_application
from jobtrack import create_app
from jobtrack.config import TestConfig
from jobtrack.db import init_db


@pytest.fixture
def csrf_client(tmp_path):
    class Config(TestConfig):
        DATABASE = str(tmp_path / "csrf.db")
        WTF_CSRF_ENABLED = True

    app = create_app(Config)
    with app.app_context():
        init_db()
    return app.test_client()


def test_post_without_csrf_token_is_rejected(csrf_client):
    response = csrf_client.post("/register", data={
        "name": "X", "email": "x@example.com", "password": "password123",
    })
    assert response.status_code == 400
    assert b"Form expired" in response.data


def test_forms_include_csrf_token(csrf_client):
    assert b'name="csrf_token"' in csrf_client.get("/register").data


def test_html_in_input_is_escaped(client, logged_in):
    add_application(client, company="<script>alert(1)</script>")
    page = client.get("/dashboard").data
    assert b"<script>alert(1)</script>" not in page
    assert b"&lt;script&gt;" in page


def test_security_headers(client):
    response = client.get("/login")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_missing_secret_key_refuses_to_start(monkeypatch):
    class NoKey(TestConfig):
        SECRET_KEY = None
    with pytest.raises(RuntimeError):
        create_app(NoKey)


def test_friendly_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert b"Page not found" in response.data
