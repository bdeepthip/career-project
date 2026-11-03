"""
Job applications: dashboard, add, edit, delete.
"""

from datetime import date

from flask import (
    Blueprint, abort, flash, g, jsonify, redirect, render_template, request,
    url_for
)
from sqlalchemy import func, or_

from . import insights
from .auth import login_required
from .models import JobApplication, JobEmail, Resume, Skill, db
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


def setup_steps(user_id, total):
    """The getting-started list on a new account's dashboard. Each step
    is checked with a small EXISTS-style query, never by loading rows."""

    def has(model):
        return db.session.query(model.id).filter_by(user_id=user_id).first() is not None

    return [
        {"title": "Add your first application", "done": total > 0,
         "text": "Every job you apply to, in one list and on the board.",
         "url": url_for("applications.add_application"), "action": "Add application"},
        {"title": "Add your skills", "done": has(Skill),
         "text": "GAJ uses them to show how well you match each job.",
         "url": url_for("profile.profile"), "action": "Open profile"},
        {"title": "Upload your resume", "done": has(Resume),
         "text": "Saved once, then sent with every Easy Apply.",
         "url": url_for("profile.profile"), "action": "Open profile"},
        {"title": "Forward one job email", "done": has(JobEmail),
         "text": "Use your GAJ address and the matching status updates itself.",
         "url": url_for("inbox.inbox"), "action": "Open inbox"},
    ]


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

    weeks = insights.weekly_counts(g.user.id)
    setup = setup_steps(g.user.id, sum(counts.values()))

    return render_template(
        "applications/dashboard.html",
        applications=applications,
        counts=counts,
        total=sum(counts.values()),
        chart=insights.chart_bars(weeks),
        this_week=weeks[-1]["count"],
        last_week=weeks[-2]["count"],
        pipeline=insights.pipeline(counts),
        rates=insights.rates(counts),
        setup=setup,
        setup_left=sum(1 for step in setup if not step["done"]),
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


@bp.route("/board")
@login_required
def board():
    """The same applications as the dashboard, as one column per
    status. Cards can be dragged between columns, or moved with the
    small status menu on each card (which also works without
    JavaScript and with a keyboard)."""

    if g.user.is_employer:
        return redirect(url_for("employer.posts"))

    applications = (JobApplication.query.filter_by(user_id=g.user.id)
                    .order_by(JobApplication.date_applied.desc(),
                              JobApplication.id.desc()).all())
    columns = {status: [] for status in STATUSES}
    for application in applications:
        columns.setdefault(application.status, []).append(application)

    return render_template("applications/board.html", columns=columns,
                           statuses=STATUSES, total=len(applications))


@bp.route("/applications/<int:application_id>/status", methods=["POST"])
@login_required
def move_application(application_id):
    """Change only the status. The board calls this with fetch() and
    gets JSON back; the menu fallback posts a normal form and is sent
    back to the board."""

    application = get_application(application_id)
    status = (request.form.get("status") or "").strip()
    wants_json = request.accept_mimetypes.best == "application/json"

    if status not in STATUSES:
        if wants_json:
            return jsonify(error="Choose a valid status."), 400
        flash("Choose a valid status.", "error")
        return redirect(url_for("applications.board"))

    application.status = status
    db.session.commit()

    if wants_json:
        return jsonify(id=application.id, status=status)
    flash(f"Moved {application.company} to {status}.", "success")
    return redirect(url_for("applications.board"))
