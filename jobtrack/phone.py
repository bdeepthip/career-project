"""
Phone numbers: add a verified mobile number in Account, then log in
with a text-message code instead of a password.

Privacy: the log-in page never reveals whether a number has an account.
It always says "if this number is linked to an account, we texted it a
code", and only texts numbers that really are linked (no cost, no spam
to strangers).
"""

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
)
from sqlalchemy.exc import IntegrityError

from .auth import login_required, safe_next, start_session
from .extensions import limiter
from .models import User, db
from .sms import (
    SmsError, check_code, display_phone, masked_phone, normalize_phone, send_code, sms_enabled
)

bp = Blueprint("phone", __name__)


def submitted_phone():
    """Rate-limit key: the number typed (or the one waiting for its code)."""
    raw = request.form.get("phone") or session.get("login_phone") or session.get("pending_phone") or ""
    return "phone:" + (normalize_phone(raw) or raw.strip()[:40])


@bp.app_context_processor
def phone_settings():
    return {"phone_login_enabled": sms_enabled(), "display_phone": display_phone}


@bp.before_request
def only_when_enabled():
    if not sms_enabled():
        abort(404)


# ---------- Log in with a text code ----------

@bp.route("/login/phone", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
@limiter.limit("3 per 15 minutes;10 per day", methods=["POST"], key_func=submitted_phone)
def login_phone():
    if g.user:
        return redirect(url_for("applications.dashboard"))

    if request.method == "POST":
        raw = request.form.get("phone") or ""
        phone = normalize_phone(raw)
        if phone is None:
            flash("Enter a 10-digit US or Canadian mobile number.", "error")
            return render_template("auth/login_phone.html", phone=raw[:40]), 400

        user = User.query.filter_by(phone=phone).first()
        if user is not None:
            try:
                send_code(phone)
            except SmsError as error:
                flash(str(error), "error")
                return render_template("auth/login_phone.html", phone=raw[:40]), 503

        session["login_phone"] = phone
        session["login_next"] = safe_next(request.args.get("next"))
        flash(f"If {masked_phone(phone)} is linked to a GAJ account, we just texted it a "
              "6-digit code.", "success")
        return redirect(url_for("phone.login_phone_code"))

    return render_template("auth/login_phone.html")


@bp.route("/login/phone/code", methods=["GET", "POST"])
@limiter.limit("30 per hour", methods=["POST"])
@limiter.limit("10 per 15 minutes", methods=["POST"], key_func=submitted_phone)
def login_phone_code():
    if g.user:
        return redirect(url_for("applications.dashboard"))

    phone = session.get("login_phone")
    if not phone:
        return redirect(url_for("phone.login_phone"))

    if request.method == "POST":
        user = User.query.filter_by(phone=phone).first()
        if user is not None and check_code(phone, request.form.get("code")):
            next_url = session.get("login_next")
            start_session(user)   # clears the session, including login_phone
            return redirect(next_url or url_for("applications.dashboard"))

        flash("That code is wrong or has expired. Check the text, or send a new code.", "error")
        return render_template("auth/login_phone_code.html", phone=phone), 401

    return render_template("auth/login_phone_code.html", phone=phone)


# ---------- Add, verify, remove a phone number (Account) ----------

@bp.route("/account/phone", methods=["POST"])
@login_required
@limiter.limit("5 per hour", key_func=lambda: f"user:{g.user.id}")
def add_phone():
    phone = normalize_phone(request.form.get("phone"))
    if phone is None:
        flash("Enter a 10-digit US or Canadian mobile number.", "error")
        return redirect(url_for("account.settings") + "#phone")

    owner = User.query.filter_by(phone=phone).first()
    if owner is not None and owner.id != g.user.id:
        flash("That number is already linked to another GAJ account.", "error")
        return redirect(url_for("account.settings") + "#phone")

    try:
        send_code(phone)
    except SmsError as error:
        flash(str(error), "error")
        return redirect(url_for("account.settings") + "#phone")

    session["pending_phone"] = phone
    flash(f"We texted a 6-digit code to {display_phone(phone)}.", "success")
    return redirect(url_for("phone.verify_phone"))


@bp.route("/account/phone/verify", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per 15 minutes", methods=["POST"], key_func=lambda: f"user:{g.user.id}")
def verify_phone():
    phone = session.get("pending_phone")
    if not phone:
        return redirect(url_for("account.settings") + "#phone")

    if request.method == "POST":
        if not check_code(phone, request.form.get("code")):
            flash("That code is wrong or has expired. Check the text, or send a new code.", "error")
            return render_template("account/verify_phone.html", phone=phone), 400

        g.user.phone = phone
        try:
            db.session.commit()
        except IntegrityError:   # someone else verified the same number a moment ago
            db.session.rollback()
            flash("That number is already linked to another GAJ account.", "error")
            return redirect(url_for("account.settings") + "#phone")

        session.pop("pending_phone", None)
        flash(f"{display_phone(phone)} is verified. You can now log in with a text code.", "success")
        return redirect(url_for("account.settings") + "#phone")

    return render_template("account/verify_phone.html", phone=phone)


@bp.route("/account/phone/remove", methods=["POST"])
@login_required
def remove_phone():
    g.user.phone = None
    db.session.commit()
    flash("Phone number removed. Log in with your email and password.", "success")
    return redirect(url_for("account.settings") + "#phone")
