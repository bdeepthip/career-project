"""
Shared test setup. Each test gets a brand-new empty database,
so tests never touch your real database.db.

By default that is a temporary SQLite file. To run the same tests
against PostgreSQL, point TEST_DATABASE_URL at an EMPTY database
that may be wiped, e.g.
    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost/jobtrack_test
"""

import os

import pytest
from sqlalchemy import text

from jobtrack import create_app
from jobtrack.config import TestConfig, normalize_url
from jobtrack.db import init_db
from jobtrack.models import db
from jobtrack.seed_data import seed


def make_app(tmp_path, **settings):
    url = os.environ.get("TEST_DATABASE_URL")
    settings["SQLALCHEMY_DATABASE_URI"] = (
        normalize_url(url) if url else f"sqlite:///{tmp_path / 'test.db'}"
    )
    config = type("Config", (TestConfig,), settings)
    app = create_app(config)
    with app.app_context():
        init_db()  # runs the real migrations, the same way production does
    return app


def wipe(app):
    """Leave the database empty for the next test (matters on PostgreSQL;
    a SQLite temp file is simply thrown away)."""
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.session.execute(text("DROP TABLE IF EXISTS alembic_version"))
        db.session.commit()
        db.engine.dispose()


@pytest.fixture
def app(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        seed()
    yield app
    wipe(app)


@pytest.fixture
def client(app):
    return app.test_client()


class AuthActions:
    def __init__(self, client):
        self.client = client

    def register(self, name="Test User", email="test@example.com", password="password123"):
        return self.client.post(
            "/register", data={"name": name, "email": email, "password": password}
        )

    def login(self, email="test@example.com", password="password123"):
        return self.client.post("/login", data={"email": email, "password": password})

    def logout(self):
        return self.client.post("/logout")


@pytest.fixture
def auth(client):
    return AuthActions(client)


@pytest.fixture
def logged_in(auth):
    auth.register()
    auth.login()
    return auth


def add_application(client, **overrides):
    data = {
        "company": "Microsoft",
        "job_title": "Software Engineer",
        "location": "Philadelphia, PA",
        "job_url": "https://careers.microsoft.com/job/1",
        "date_applied": "2026-10-20",
        "status": "Applied",
        "notes": "",
    }
    data.update(overrides)
    # follow_redirects consumes the "Added X." message, so later page checks
    # only see the table, not the flash message
    return client.post("/applications/add", data=data, follow_redirects=True)
