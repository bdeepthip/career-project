"""
Accounts: register, log in, log out, and the login_required helper.
"""

import functools
import sqlite3
from urllib.parse import urlparse

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .validation import MIN_PASSWORD_LENGTH, clean, is_valid_email

bp = Blueprint("auth", __name__)


@bp.before_app_request
def load_logged_in_user():
    """Runs before every request: puts the current user on g.user
    (or None), so routes and templates can use it."""

    user_id = session.get("user_id")
    g.user = None

    if user_id is not None:
        g.user = get_db().execute(
            "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        # The account no longer exists: clear the stale session
        if g.user is None:
            session.clear()


def login_required(view):
    """Put @login_required above a route to make it members-only.
    Replaces the `if "user_id" not in session` check that was
    copied into every route."""

    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)

    return wrapped


def safe_next(target):
    """Only redirect to pages on this site after login.
    Blocks links like /login?next=https://evil.example."""
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/"):
        return None
    return target


@bp.route("/")
def home():
    if g.user:
        return redirect(url_for("applications.dashboard"))
    return render_template("index.html")


@bp.route("/register", methods=["GET", "POST"])
def register():

    if g.user:
        return redirect(url_for("applications.dashboard"))

    if request.method == "POST":
        name = clean(request.form, "name", 100)
        email = clean(request.form, "email", 254).lower()
        password = request.form.get("password") or ""

        error = None
        if not name or not email or not password:
            error = "All fields are required."
        elif not is_valid_email(email):
            error = "Enter a valid email address."
        elif len(password) < MIN_PASSWORD_LENGTH:
            error = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."

        if error is None:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password)),
                )
                db.commit()
            except sqlite3.IntegrityError:
                # UNIQUE(email) caught a duplicate. Checking first and then
                # inserting can race; letting the database decide cannot.
                error = "An account with this email already exists."
            else:
                flash("Account created. Log in to get started.", "success")
                return redirect(url_for("auth.login"))

        flash(error, "error")
        return render_template("auth/register.html", name=name, email=email), 400

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():

    if g.user:
        return redirect(url_for("applications.dashboard"))

    if request.method == "POST":
        email = clean(request.form, "email", 254).lower()
        password = request.form.get("password") or ""

        user = get_db().execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

        # Same message whether the email or the password is wrong,
        # so nobody can use this form to find out who has an account.
        if user is None or not check_password_hash(user["password"], password):
            flash("Incorrect email or password.", "error")
            return render_template("auth/login.html", email=email), 401

        # New session on login: stops an attacker who planted a
        # session cookie beforehand from riding along
        session.clear()
        session["user_id"] = user["id"]

        return redirect(
            safe_next(request.args.get("next")) or url_for("applications.dashboard")
        )

    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    # POST only (with a CSRF token), so another site can't log you out
    session.clear()
    flash("You're logged out.", "success")
    return redirect(url_for("auth.login"))
