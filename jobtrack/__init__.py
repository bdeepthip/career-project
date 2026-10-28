"""
JobTrack application factory.

create_app() builds the Flask app: loads settings, connects the
database helper, turns on CSRF protection, and registers each
section of the site (a "blueprint" is one section with its routes).
"""

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError, CSRFProtect

from . import db
from .config import get_config

csrf = CSRFProtect()


def create_app(config_class=None):
    app = Flask(__name__)
    app.config.from_object(config_class or get_config())

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY is not set. Add SECRET_KEY=<a long random string> "
            "to your .env file."
        )

    db.init_app(app)
    csrf.init_app(app)

    from .auth import bp as auth_bp
    from .applications import bp as applications_bp
    from .profile import bp as profile_bp
    from .jobs import bp as jobs_bp
    from .inbox import bp as inbox_bp
    from .account import bp as account_bp
    from .inbound import bp as inbound_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(applications_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(inbox_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(inbound_bp)
    # Email services can't send a CSRF token; the webhook checks its own secret
    csrf.exempt("jobtrack.inbound.receive")

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
        # Stop other sites from showing JobTrack inside a frame
        response.headers["X-Frame-Options"] = "DENY"
        # Stop browsers from guessing file types
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Don't send full page URLs to other sites
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
