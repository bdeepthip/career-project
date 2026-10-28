"""
Jobs feed, job details, and the Match Checker.
"""

from flask import Blueprint, abort, g, render_template, request
from sqlalchemy import or_

from .auth import login_required
from .matching import (
    build_learning_plan, calculate_match, extract_skills, get_user_skills
)
from .models import Job, db
from .profile import DOMAINS
from .validation import clean

bp = Blueprint("jobs", __name__)


@bp.route("/jobs")
@login_required
def jobs():
    search = request.args.get("search", "").strip()[:100]
    domain = request.args.get("domain", "").strip()
    if domain not in DOMAINS:
        domain = ""
    location = request.args.get("location", "").strip()[:100]

    query = Job.query

    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Job.title.ilike(pattern),
                                 Job.company.ilike(pattern),
                                 Job.required_skills.ilike(pattern)))
    if domain:
        query = query.filter_by(domain=domain)
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))

    # Load the user's skills ONCE (not once per job)
    user_skills = get_user_skills(g.user.id)

    jobs_data = []
    for job in query.order_by(Job.posted_date.desc()):
        job_dict = job.to_dict()
        job_dict["match_score"], _, _ = calculate_match(user_skills, job.required_skills)
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
    job = db.session.get(Job, job_id)
    if job is None:
        abort(404)

    user_skills = get_user_skills(g.user.id)
    match_score, matched, missing = calculate_match(user_skills, job.required_skills)
    learning_plan, total_hours = build_learning_plan(missing)

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
    user_skills = get_user_skills(g.user.id)

    if request.method == "POST":
        job_description = clean(request.form, "job_description", 20000)
        required = extract_skills(job_description)

        match_score, matched, missing = calculate_match(user_skills, required)
        learning_plan, total_hours = build_learning_plan(missing)

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
