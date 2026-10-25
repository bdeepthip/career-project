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
from .db import get_db
from .validation import MIN_PASSWORD_LENGTH, clean

bp = Blueprint("account", __name__)

# Every table that holds a user's data, in the order to delete them
# (rows that point at other rows go first)
USER_TABLES = [
    "job_emails",
    "job_applications",
    "skills",
    "education",
    "experience",
    "profiles",
]


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

    db = get_db()
    db.execute("UPDATE users SET name = ? WHERE id = ?", (name, g.user["id"]))
    db.commit()
    flash("Name updated.", "success")
    return redirect(url_for("account.settings"))


@bp.route("/account/password", methods=["POST"])
@login_required
def change_password():
    current = request.form.get("current_password") or ""
    new = request.form.get("new_password") or ""
    confirm = request.form.get("confirm_password") or ""

    if not check_password_hash(g.user["password"], current):
        flash("Your current password is incorrect.", "error")
    elif len(new) < MIN_PASSWORD_LENGTH:
        flash(f"New password must be at least {MIN_PASSWORD_LENGTH} characters.", "error")
    elif new != confirm:
        flash("The two new passwords don't match.", "error")
    else:
        db = get_db()
        db.execute("UPDATE users SET password = ? WHERE id = ?",
                   (generate_password_hash(new), g.user["id"]))
        db.commit()

        # Other devices are signed out (their session no longer matches the
        # new password); keep THIS device logged in with a fresh session
        user = db.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
        start_session(user)

        flash("Password changed. Other devices have been signed out.", "success")

    return redirect(url_for("account.settings"))


def _rows(db, query, params):
    return [dict(row) for row in db.execute(query, params)]


@bp.route("/account/export")
@login_required
def export_data():
    """Download everything JobTrack stores about you, as JSON."""
    db = get_db()
    uid = g.user["id"]

    profile = db.execute(
        """SELECT headline, phone, location, domain, target_role, experience_level,
                  preferred_location, about
           FROM profiles WHERE user_id = ?""", (uid,)
    ).fetchone()

    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "account": {"name": g.user["name"], "email": g.user["email"]},
        "profile": dict(profile) if profile else None,
        "skills": [r["skill_name"] for r in db.execute(
            "SELECT skill_name FROM skills WHERE user_id = ? ORDER BY skill_name", (uid,))],
        "education": _rows(db, """SELECT institution, degree, field_of_study, start_year, end_year
                                   FROM education WHERE user_id = ?""", (uid,)),
        "experience": _rows(db, """SELECT company, job_title, location, start_date, end_date, description
                                    FROM experience WHERE user_id = ?""", (uid,)),
        "applications": _rows(db, """SELECT id, company, job_title, location, job_url,
                                            date_applied, status, notes
                                     FROM job_applications WHERE user_id = ?
                                     ORDER BY date_applied""", (uid,)),
        "inbox_emails": _rows(db, """SELECT sender, subject, body, received_at, detected_status,
                                            application_id, update_note
                                     FROM job_emails WHERE user_id = ?
                                     ORDER BY received_at""", (uid,)),
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

    if not check_password_hash(g.user["password"], password):
        flash("Password incorrect. Your account was not deleted.", "error")
        return redirect(url_for("account.settings") + "#delete")

    db = get_db()
    uid = g.user["id"]

    # One transaction: either everything is deleted, or nothing is
    with db:
        for table in USER_TABLES:
            db.execute(f"DELETE FROM {table} WHERE user_id = ?", (uid,))
        db.execute("DELETE FROM users WHERE id = ?", (uid,))

    session.clear()
    flash("Your account and all your data have been permanently deleted.", "success")
    return redirect(url_for("auth.login"))
