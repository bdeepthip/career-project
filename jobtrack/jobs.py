"""
Jobs feed, job details, and the Match Checker.
"""

from flask import Blueprint, abort, g, render_template, request

from .auth import login_required
from .db import get_db
from .matching import (
    build_learning_plan, calculate_match, extract_skills, get_user_skills
)
from .profile import DOMAINS
from .validation import clean

bp = Blueprint("jobs", __name__)


@bp.route("/jobs")
@login_required
def jobs():
    db = get_db()

    search = request.args.get("search", "").strip()[:100]
    domain = request.args.get("domain", "").strip()
    if domain not in DOMAINS:
        domain = ""
    location = request.args.get("location", "").strip()[:100]

    query = "SELECT * FROM jobs WHERE 1 = 1"
    params = []

    if search:
        query += " AND (title LIKE ? OR company LIKE ? OR required_skills LIKE ?)"
        params += [f"%{search}%"] * 3
    if domain:
        query += " AND domain = ?"
        params.append(domain)
    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")

    query += " ORDER BY posted_date DESC"

    # Load the user's skills ONCE (was once per job)
    user_skills = get_user_skills(db, g.user["id"])

    jobs_data = []
    for job in db.execute(query, params):
        job_dict = dict(job)
        job_dict["match_score"], _, _ = calculate_match(user_skills, job["required_skills"])
        jobs_data.append(job_dict)

    return render_template(
        "jobs/jobs.html",
        jobs=jobs_data,
        domains=DOMAINS,
        search=search,
        domain=domain,
        location=location,
        has_skills=bool(user_skills),
    )


@bp.route("/jobs/<int:job_id>")
@login_required
def job_details(job_id):
    db = get_db()

    job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        abort(404)

    user_skills = get_user_skills(db, g.user["id"])
    match_score, matched, missing = calculate_match(user_skills, job["required_skills"])
    learning_plan, total_hours = build_learning_plan(db, missing)

    return render_template(
        "jobs/job_details.html",
        job=job,
        match_score=match_score,
        matched=matched,
        missing=missing,
        learning_plan=learning_plan,
        total_hours=total_hours,
        has_skills=bool(user_skills),
    )


@bp.route("/match", methods=["GET", "POST"])
@login_required
def match_checker():
    job_description = ""
    result = None
    db = get_db()
    user_skills = get_user_skills(db, g.user["id"])

    if request.method == "POST":
        job_description = clean(request.form, "job_description", 20000)
        required = extract_skills(job_description)

        match_score, matched, missing = calculate_match(user_skills, required)
        learning_plan, total_hours = build_learning_plan(db, missing)

        result = {
            "match_score": match_score,
            "matched": matched,
            "missing": missing,
            "learning_plan": learning_plan,
            "total_hours": total_hours,
            "found_any": bool(required),
        }

    return render_template(
        "jobs/match.html",
        job_description=job_description,
        result=result,
        has_skills=bool(user_skills),
    )
