"""
Account settings: change name, change password, export data, delete account.
"""

import json
from datetime import date, datetime, timezone

from flask import (
    Blueprint, Response, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from .auth import login_required, start_session
from .inbox import forwarding_address
from .models import (
    Education, Experience, JobApplication, JobEmail, Profile, Skill, User, db
)
from .validation import MIN_PASSWORD_LENGTH, clean

bp = Blueprint("account", __name__)

# Every table that holds a user's data, in the order to delete them
# (rows that point at other rows go first)
USER_MODELS = [JobEmail, JobApplication, Skill, Education, Experience, Profile]


@bp.route("/account")
@login_required
def settings():
    return render_template("account/settings.html")


@bp.route("/account/name", methods=["POST"])
@login_required
def change_name():
    name = clean(request.form, "name", 100)
    if not name:
        flash("Name can't be empty.", "error")
        return redirect(url_for("account.settings"))

    g.user.name = name
    db.session.commit()
    flash("Name updated.", "success")
    return redirect(url_for("account.settings"))


@bp.route("/account/password", methods=["POST"])
@login_required
def change_password():
    current = request.form.get("current_password") or ""
    new = request.form.get("new_password") or ""
    confirm = request.form.get("confirm_password") or ""

    if not check_password_hash(g.user.password, current):
        flash("Your current password is incorrect.", "error")
    elif len(new) < MIN_PASSWORD_LENGTH:
        flash(f"New password must be at least {MIN_PASSWORD_LENGTH} characters.", "error")
    elif new != confirm:
        flash("The two new passwords don't match.", "error")
    else:
        g.user.password = generate_password_hash(new)
        db.session.commit()

        # Other devices are signed out (their session no longer matches the
        # new password); keep THIS device logged in with a fresh session
        start_session(g.user)

        flash("Password changed. Other devices have been signed out.", "success")

    return redirect(url_for("account.settings"))


def _rows(model, fields, order_by=None):
    query = model.query.filter_by(user_id=g.user.id)
    if order_by is not None:
        query = query.order_by(order_by)
    return [{f: getattr(row, f) for f in fields} for row in query]


@bp.route("/account/export")
@login_required
def export_data():
    """Download everything JobTrack stores about you, as JSON."""
    profile = Profile.query.filter_by(user_id=g.user.id).first()
    profile_fields = ["headline", "phone", "location", "domain", "target_role",
                      "experience_level", "preferred_location", "about"]

    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "account": {"name": g.user.name, "email": g.user.email,
                    "forwarding_address": forwarding_address(g.user)},
        "profile": {f: getattr(profile, f) for f in profile_fields} if profile else None,
        "skills": [s["skill_name"] for s in _rows(Skill, ["skill_name"], Skill.skill_name)],
        "education": _rows(Education, ["institution", "degree", "field_of_study",
                                       "start_year", "end_year"]),
        "experience": _rows(Experience, ["company", "job_title", "location",
                                         "start_date", "end_date", "description"]),
        "applications": _rows(JobApplication, ["id", "company", "job_title", "location",
                                               "job_url", "date_applied", "status", "notes"],
                              JobApplication.date_applied),
        "inbox_emails": _rows(JobEmail, ["sender", "subject", "body", "received_at",
                                         "detected_status", "application_id", "update_note"],
                              JobEmail.received_at),
    }

    filename = f"jobtrack-export-{date.today().isoformat()}.json"
    return Response(
        json.dumps(data, indent=2, ensure_ascii=False),
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get("password") or ""

    if not check_password_hash(g.user.password, password):
        flash("Password incorrect. Your account was not deleted.", "error")
        return redirect(url_for("account.settings") + "#delete")

    uid = g.user.id

    # One transaction: either everything is deleted, or nothing is
    for model in USER_MODELS:
        model.query.filter_by(user_id=uid).delete()
    User.query.filter_by(id=uid).delete()
    db.session.commit()

    session.clear()
    flash("Your account and all your data have been permanently deleted.", "success")
    return redirect(url_for("auth.login"))
