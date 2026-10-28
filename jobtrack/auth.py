"""
Accounts: register, log in, log out, and the login_required helper.
"""

import functools
import hmac
from urllib.parse import urlparse

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
)
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import limiter
from .mailer import send_email
from .models import User, db
from .tokens import make_reset_token, password_fingerprint, read_reset_token
from .validation import MIN_PASSWORD_LENGTH, clean, is_valid_email

bp = Blueprint("auth", __name__)


def submitted_email():
    """Rate-limit key: the email typed into the form, so one account can't be
    guessed at from many addresses, and one inbox can't be flooded."""
    return "email:" + (request.form.get("email") or "").strip().lower()[:254]


@bp.before_app_request
def load_logged_in_user():
    """Runs before every request: puts the current user on g.user
    (or None), so routes and templates can use it."""

    user_id = session.get("user_id")
    g.user = None

    if user_id is not None:
        user = db.session.get(User, user_id)

        # Log out if the account was deleted, or if the password changed
        # since this session logged in (password change = sign out everywhere)
        if user is None or session.get("pw") != password_fingerprint(user["password"]):
            session.clear()
        else:
            g.user = user


def start_session(user):
    """Log a user in. A fresh session stops an attacker who planted a
    session cookie beforehand from riding along."""
    session.clear()
    session["user_id"] = user["id"]
    session["pw"] = password_fingerprint(user["password"])


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
@limiter.limit("20 per hour", methods=["POST"])
def register():

    if g.user:
        return redirect(url_for("applications.dashboard"))

    if request.method == "POST":
        name = clean(request.form, "name", 100)
        email = clean(request.form, "email", 254).lower()
        password = request.form.get("password") or ""
        account_type = request.form.get("account_type")
        if account_type not in ("seeker", "employer"):
            account_type = "seeker"
        company = clean(request.form, "company", 120) if account_type == "employer" else None

        invite_code = current_app.config.get("BETA_INVITE_CODE")
        typed_code = (request.form.get("invite_code") or "").strip()

        error = None
        if invite_code and not hmac.compare_digest(typed_code.lower().encode(),
                                                   invite_code.lower().encode()):
            error = "GAJ is in private beta. Enter the invite code you were given."
        elif not name or not email or not password:
            error = "All fields are required."
        elif not is_valid_email(email):
            error = "Enter a valid email address."
        elif len(password) < MIN_PASSWORD_LENGTH:
            error = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        elif account_type == "employer" and not company:
            error = "Enter the company you're hiring for."

        if error is None:
            try:
                db.session.add(User(name=name, email=email,
                                    password=generate_password_hash(password),
                                    account_type=account_type, company=company))
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                # UNIQUE(email) caught a duplicate. Checking first and then
                # inserting can race; letting the database decide cannot.
                error = "An account with this email already exists."
            else:
                flash("Account created. Log in to get started.", "success")
                return redirect(url_for("auth.login"))

        flash(error, "error")
        return render_template("auth/register.html", name=name, email=email,
                               invite_code=typed_code, account_type=account_type,
                               company=company), 400

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("30 per minute;300 per hour", methods=["POST"])
@limiter.limit("10 per 15 minutes", methods=["POST"], key_func=submitted_email)
def login():

    if g.user:
        return redirect(url_for("applications.dashboard"))

    if request.method == "POST":
        email = clean(request.form, "email", 254).lower()
        password = request.form.get("password") or ""

        user = User.query.filter_by(email=email).first()

        # Same message whether the email or the password is wrong,
        # so nobody can use this form to find out who has an account.
        if user is None or not check_password_hash(user["password"], password):
            flash("Incorrect email or password.", "error")
            return render_template("auth/login.html", email=email), 401

        start_session(user)

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


@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("20 per hour", methods=["POST"])
@limiter.limit("3 per hour", methods=["POST"], key_func=submitted_email)
def forgot_password():

    if request.method == "POST":
        email = clean(request.form, "email", 254).lower()

        user = User.query.filter_by(email=email).first()

        if user is not None:
            link = url_for("auth.reset_password",
                           token=make_reset_token(user), _external=True)
            send_email(
                user["email"],
                "Reset your GAJ password",
                f"Hi {user['name']},\n\n"
                f"Someone asked to reset the password for your GAJ account. "
                f"To choose a new password, open this link within 1 hour:\n\n"
                f"{link}\n\n"
                f"If this wasn't you, ignore this email. Your password stays the same.\n",
            )

        # Same message either way, so this page can't reveal who has an account
        flash("If an account exists for that email, we've sent a link to reset "
              "your password. It expires in 1 hour.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


def _user_for_token(token):
    """The user a reset token belongs to, or None if the token is invalid,
    expired, or already used (the password changed since it was made)."""
    data = read_reset_token(token)
    if data is None:
        return None
    user_id, fingerprint = data
    user = db.session.get(User, user_id)
    if user is None or password_fingerprint(user["password"]) != fingerprint:
        return None
    return user


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("20 per hour", methods=["POST"])
def reset_password(token):
    user = _user_for_token(token)

    if user is None:
        flash("That reset link is invalid or has expired. Request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if len(password) < MIN_PASSWORD_LENGTH:
            flash(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", "error")
        elif password != confirm:
            flash("The two passwords don't match.", "error")
        else:
            user.password = generate_password_hash(password)
            db.session.commit()
            # Changing the password makes this link (and every older one)
            # stop working, and signs out every logged-in device
            flash("Your password was reset. Log in with your new password.", "success")
            return redirect(url_for("auth.login"))

        return render_template("auth/reset_password.html", token=token), 400

    return render_template("auth/reset_password.html", token=token)
