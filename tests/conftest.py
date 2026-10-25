"""
Shared test setup. Each test gets a brand-new temporary database,
so tests never touch your real database.db.
"""

import pytest

from jobtrack import create_app
from jobtrack.config import TestConfig
from jobtrack.db import get_db, init_db
from jobtrack.seed_data import seed


@pytest.fixture
def app(tmp_path):
    class Config(TestConfig):
        DATABASE = str(tmp_path / "test.db")

    app = create_app(Config)
    with app.app_context():
        init_db()
        seed(get_db())
    yield app


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
