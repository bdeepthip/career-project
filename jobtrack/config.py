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


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Keeps using your existing database.db in the project folder
    DATABASE = os.environ.get(
        "DATABASE", os.path.join(PROJECT_ROOT, "database.db")
    )

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
    MAIL_FROM = os.environ.get("MAIL_FROM", "JobTrack <no-reply@localhost>")

    PASSWORD_RESET_MAX_AGE = 60 * 60  # reset links expire after 1 hour

    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False  # individual tests turn this back on


def get_config():
    if os.environ.get("FLASK_ENV") == "production":
        return ProductionConfig
    return DevelopmentConfig
