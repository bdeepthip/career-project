"""
Job applications: dashboard, add, edit, delete.
"""

from datetime import date

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)
from sqlalchemy import func, or_

from .auth import login_required
from .models import JobApplication, JobEmail, db
from .validation import STATUSES, validate_application

bp = Blueprint("applications", __name__)

FORM_FIELDS = ["company", "job_title", "location", "job_url",
               "date_applied", "status", "notes"]


def get_application(application_id):
    """Fetch one application that belongs to the logged-in user.
    Someone else's id gives 404, the same as an id that doesn't
    exist, so it never reveals that the record is there."""

    application = JobApplication.query.filter_by(
        id=application_id, user_id=g.user.id
    ).first()

    if application is None:
        abort(404)
    return application


@bp.route("/dashboard")
@login_required
def dashboard():
    if g.user.is_employer:
        return redirect(url_for("employer.posts"))
    search = request.args.get("search", "").strip()[:100]
    status_filter = request.args.get("status", "").strip()
    if status_filter not in STATUSES:
        status_filter = ""

    query = JobApplication.query.filter_by(user_id=g.user.id)

    if search:
        pattern = f"%{search}%"
        # ilike = case-insensitive LIKE on both SQLite and PostgreSQL
        query = query.filter(or_(JobApplication.company.ilike(pattern),
                                 JobApplication.job_title.ilike(pattern)))

    if status_filter:
        query = query.filter_by(status=status_filter)

    applications = query.order_by(JobApplication.date_applied.desc(),
                                  JobApplication.id.desc()).all()

    # One query for all the counts: SELECT status, COUNT(*) ... GROUP BY status
    counts = {status: 0 for status in STATUSES}
    rows = (db.session.query(JobApplication.status, func.count())
            .filter(JobApplication.user_id == g.user.id)
            .group_by(JobApplication.status))
    for status, n in rows:
        counts[status] = n

    return render_template(
        "applications/dashboard.html",
        applications=applications,
        counts=counts,
        total=sum(counts.values()),
        statuses=STATUSES,
        search=search,
        status_filter=status_filter,
        today_label=date.today().strftime("%A, %B %-d"),
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

        db.session.add(JobApplication(user_id=g.user.id, **data))
        db.session.commit()

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

        for field in FORM_FIELDS:
            setattr(application, field, data[field])
        db.session.commit()

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
    company = application.company

    # Unlink inbox emails first so they don't point at a deleted row
    JobEmail.query.filter_by(application_id=application.id, user_id=g.user.id) \
        .update({"application_id": None})
    db.session.delete(application)
    db.session.commit()

    flash(f"Deleted {company}.", "success")
    return redirect(url_for("applications.dashboard"))
