"""
App settings, read from environment variables (your .env file).

Development (your laptop):  FLASK_ENV is unset or "development"
Production (public server): set FLASK_ENV=production
"""

import os

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load .env from the project folder BEFORE the settings below read it.
# (Reading settings first and loading .env later left SECRET_KEY empty
# when starting the app with `python app.py`.)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def database_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        return "sqlite:///" + os.path.join(PROJECT_ROOT, "database.db")
    return normalize_url(url)


def normalize_url(url):
    # Hosting providers often hand out "postgres://..." URLs; SQLAlchemy needs
    # "postgresql+psycopg://..." to use the psycopg 3 driver.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Which database to use. On your laptop, leave DATABASE_URL unset and
    # GAJ keeps using database.db in the project folder (SQLite).
    # In production, set DATABASE_URL to your PostgreSQL address, e.g.
    #   postgresql://user:password@host:5432/jobtrack
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}  # reconnect if the DB restarted

    # Session cookie safety
    SESSION_COOKIE_HTTPONLY = True      # JavaScript can't read the cookie
    SESSION_COOKIE_SAMESITE = "Lax"     # other sites can't send it with forms
    SESSION_COOKIE_SECURE = False       # True in production (HTTPS only)

    # Reject huge form posts (a pasted email is a few KB at most)
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024  # 1 MB

    WTF_CSRF_TIME_LIMIT = None  # CSRF token valid for the whole session

    # Outgoing email (password reset links). Works with any SMTP service:
    # Gmail (with an App Password), Resend, SendGrid, Postmark...
    # If MAIL_SERVER is empty, emails are printed in the terminal instead,
    # which is what you want on your laptop.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "GAJ <no-reply@localhost>")

    PASSWORD_RESET_MAX_AGE = 60 * 60  # reset links expire after 1 hour

    # Incoming email (each user's forwarding address, jt-xxxx@INBOUND_DOMAIN).
    # An email service receives mail for INBOUND_DOMAIN and posts each email to
    # /inbound/email with INBOUND_WEBHOOK_SECRET. Leave the secret empty and
    # the webhook stays switched off.
    INBOUND_DOMAIN = os.environ.get("INBOUND_DOMAIN", "inbound.localhost").strip().lower()
    INBOUND_WEBHOOK_SECRET = os.environ.get("INBOUND_WEBHOOK_SECRET", "")
    INBOUND_DAILY_LIMIT = 300  # emails per user per day, so a leaked address can't flood an account

    # Shown on the Privacy and Terms pages and in the footer
    CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")
    # Optional link for beta testers to send feedback (e.g. a Google Form)
    FEEDBACK_URL = os.environ.get("FEEDBACK_URL", "")
    # Optional: during a private beta, only people with this code can sign up
    BETA_INVITE_CODE = os.environ.get("BETA_INVITE_CODE", "").strip()

    # Limits on login / sign-up / reset attempts (stops password guessing).
    # memory:// is right for one server process; set redis://... if you
    # ever run several servers.
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    PRODUCTION = False
    BEHIND_PROXY = False  # True when a host (Render) sits in front of the app

    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    PRODUCTION = True
    BEHIND_PROXY = True
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"


def check_production_settings(config):
    """Refuse to start a public server with settings that would lose data
    or make accounts easy to break into. Returns a list of problems."""
    problems = []
    if len(config.get("SECRET_KEY") or "") < 32:
        problems.append("SECRET_KEY must be at least 32 characters "
                        "(python -c \"import secrets; print(secrets.token_hex(32))\").")
    if config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        problems.append("DATABASE_URL must point to PostgreSQL. A SQLite file on a "
                        "hosting server is wiped on every deploy.")
    if not config.get("MAIL_SERVER"):
        problems.append("MAIL_SERVER is not set, so password reset emails can't be sent.")
    return problems


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False  # individual tests turn this back on
    INBOUND_DOMAIN = "in.jobtrack.test"
    INBOUND_WEBHOOK_SECRET = "test-inbound-secret"
    RATELIMIT_ENABLED = False  # tests that check limits turn this back on
    CONTACT_EMAIL = "hello@jobtrack.test"


def get_config():
    if os.environ.get("FLASK_ENV") == "production":
        return ProductionConfig
    return DevelopmentConfig
