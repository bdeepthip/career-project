"""
Job applications: dashboard, add, edit, delete.
"""

from datetime import date

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)

from .auth import login_required
from .db import get_db
from .validation import STATUSES, validate_application

bp = Blueprint("applications", __name__)


def get_application(application_id):
    """Fetch one application that belongs to the logged-in user.
    Someone else's id gives 404, the same as an id that doesn't
    exist, so it never reveals that the record is there."""

    application = get_db().execute(
        "SELECT * FROM job_applications WHERE id = ? AND user_id = ?",
        (application_id, g.user["id"]),
    ).fetchone()

    if application is None:
        abort(404)
    return application


@bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user_id = g.user["id"]

    search = request.args.get("search", "").strip()[:100]
    status_filter = request.args.get("status", "").strip()
    if status_filter not in STATUSES:
        status_filter = ""

    query = "SELECT * FROM job_applications WHERE user_id = ?"
    params = [user_id]

    if search:
        query += " AND (company LIKE ? OR job_title LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    query += " ORDER BY date_applied DESC, id DESC"
    applications = db.execute(query, params).fetchall()

    # One query for all the counts (was five separate queries)
    counts = {status: 0 for status in STATUSES}
    for row in db.execute(
        """
        SELECT status, COUNT(*) AS n
        FROM job_applications
        WHERE user_id = ?
        GROUP BY status
        """,
        (user_id,),
    ):
        counts[row["status"]] = row["n"]

    return render_template(
        "applications/dashboard.html",
        applications=applications,
        counts=counts,
        total=sum(counts.values()),
        statuses=STATUSES,
        search=search,
        status_filter=status_filter,
    )


@bp.route("/applications/add", methods=["GET", "POST"])
@login_required
def add_application():

    if request.method == "POST":
        data, errors = validate_application(request.form)

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "applications/form.html", application=data,
                statuses=STATUSES, mode="add",
            ), 400

        db = get_db()
        db.execute(
            """
            INSERT INTO job_applications
            (user_id, company, job_title, location, job_url,
             date_applied, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (g.user["id"], data["company"], data["job_title"],
             data["location"], data["job_url"], data["date_applied"],
             data["status"], data["notes"]),
        )
        db.commit()

        flash(f"Added {data['company']}.", "success")
        return redirect(url_for("applications.dashboard"))

    # Pre-fill from a job listing ("Track Application" button) and today's date
    application = {
        "company": request.args.get("company", "")[:120],
        "job_title": request.args.get("job_title", "")[:120],
        "location": request.args.get("location", "")[:120],
        "job_url": request.args.get("job_url", "")[:1000],
        "date_applied": date.today().isoformat(),
        "status": "Applied",
        "notes": "",
    }
    return render_template(
        "applications/form.html", application=application,
        statuses=STATUSES, mode="add",
    )


@bp.route("/applications/edit/<int:application_id>", methods=["GET", "POST"])
@login_required
def edit_application(application_id):
    application = get_application(application_id)

    if request.method == "POST":
        data, errors = validate_application(request.form)

        if errors:
            for error in errors:
                flash(error, "error")
            data["id"] = application_id
            return render_template(
                "applications/form.html", application=data,
                statuses=STATUSES, mode="edit",
            ), 400

        db = get_db()
        db.execute(
            """
            UPDATE job_applications
            SET company = ?, job_title = ?, location = ?, job_url = ?,
                date_applied = ?, status = ?, notes = ?
            WHERE id = ? AND user_id = ?
            """,
            (data["company"], data["job_title"], data["location"],
             data["job_url"], data["date_applied"], data["status"],
             data["notes"], application_id, g.user["id"]),
        )
        db.commit()

        flash(f"Updated {data['company']}.", "success")
        return redirect(url_for("applications.dashboard"))

    return render_template(
        "applications/form.html", application=application,
        statuses=STATUSES, mode="edit",
    )


@bp.route("/applications/delete/<int:application_id>", methods=["POST"])
@login_required
def delete_application(application_id):
    application = get_application(application_id)

    db = get_db()
    # Unlink inbox emails first so they don't point at a deleted row
    db.execute(
        "UPDATE job_emails SET application_id = NULL WHERE application_id = ? AND user_id = ?",
        (application_id, g.user["id"]),
    )
    db.execute(
        "DELETE FROM job_applications WHERE id = ? AND user_id = ?",
        (application_id, g.user["id"]),
    )
    db.commit()

    flash(f"Deleted {application['company']}.", "success")
    return redirect(url_for("applications.dashboard"))
