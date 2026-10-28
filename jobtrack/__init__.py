"""
GAJ application factory.

create_app() builds the Flask app: loads settings, connects the
database, turns on CSRF protection and rate limits, and registers each
section of the site (a "blueprint" is one section with its routes).
"""

import logging

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError
from sqlalchemy import text
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db
from .config import check_production_settings, get_config
from .extensions import csrf, limiter

# Strict browser rules: only run scripts and styles served by GAJ
# itself, so injected HTML can't load or run anything
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "object-src 'none'",
])


def create_app(config_class=None):
    app = Flask(__name__)
    app.config.from_object(config_class or get_config())

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY is not set. Add SECRET_KEY=<a long random string> "
            "to your .env file."
        )
    if app.config.get("PRODUCTION"):
        problems = check_production_settings(app.config)
        if problems:
            raise RuntimeError("Not safe to start in production:\n- " + "\n- ".join(problems))

    if app.config.get("BEHIND_PROXY"):
        # The host's proxy talks to us over plain HTTP; trust its headers for
        # the visitor's real IP (rate limits) and https:// (links in emails)
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    if not app.debug and not app.testing:
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from .auth import bp as auth_bp
    from .applications import bp as applications_bp
    from .profile import bp as profile_bp
    from .jobs import bp as jobs_bp
    from .inbox import bp as inbox_bp
    from .account import bp as account_bp
    from .inbound import bp as inbound_bp
    from .pages import bp as pages_bp
    from .activity import bp as activity_bp
    from .phone import bp as phone_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(applications_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(inbox_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(inbound_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(activity_bp)
    app.register_blueprint(phone_bp)
    # Email services can't send a CSRF token; the webhook checks its own secret
    csrf.exempt("jobtrack.inbound.receive")

    @app.context_processor
    def site_settings():
        from .daily import line_for
        return {
            "contact_email": app.config.get("CONTACT_EMAIL"),
            "feedback_url": app.config.get("FEEDBACK_URL"),
            "daily_line": line_for(),
        }

    from .timefmt import month_label, time_ago
    app.add_template_filter(time_ago, "time_ago")
    app.add_template_filter(month_label, "month_label")

    @app.route("/healthz")
    @limiter.exempt
    def healthz():
        """For the host's uptime checks: is the app up and the database reachable?"""
        try:
            db.db.session.execute(text("SELECT 1"))
        except Exception:
            app.logger.exception("Health check: database unreachable")
            return {"status": "database unreachable"}, 503
        return {"status": "ok"}

    register_error_pages(app)
    register_security_headers(app)

    return app


def register_error_pages(app):

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/error.html",
                               title="Page not found",
                               message="That page doesn't exist or was moved."), 404

    @app.errorhandler(413)
    def too_large(error):
        return render_template("errors/error.html",
                               title="Too much text",
                               message="That submission is too large. Shorten it and try again."), 413

    @app.errorhandler(429)
    def too_many_requests(error):
        return render_template("errors/error.html",
                               title="Too many attempts",
                               message="Too many attempts from your connection. "
                                       "Wait a few minutes and try again."), 429

    @app.errorhandler(CSRFError)
    def csrf_failed(error):
        return render_template("errors/error.html",
                               title="Form expired",
                               message="Your form session expired. Go back, refresh the page, and try again."), 400

    @app.errorhandler(500)
    def server_error(error):
        return render_template("errors/error.html",
                               title="Something went wrong",
                               message="An unexpected error happened. Try again in a moment."), 500


def register_security_headers(app):

    @app.after_request
    def add_headers(response):
        # Stop other sites from showing GAJ inside a frame
        response.headers["X-Frame-Options"] = "DENY"
        # Stop browsers from guessing file types
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Don't send full page URLs to other sites
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if app.config.get("PRODUCTION"):
            # Browsers remember to use HTTPS only, for a year
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
