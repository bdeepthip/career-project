"""
Jobs feed, job details, and the Match Checker.
"""

from datetime import datetime, timedelta

from flask import Blueprint, abort, g, render_template, request
from sqlalchemy import or_

from .auth import login_required
from .matching import (
    build_learning_plan, calculate_match, extract_skills, get_user_skills
)
from .models import Job, Submission, db
from .profile import DOMAINS
from .validation import clean

bp = Blueprint("jobs", __name__)

# "Date posted" filter: value -> (label, how far back)
POSTED_WINDOWS = {
    "1": ("Past 24 hours", timedelta(hours=24)),
    "3": ("Past 3 days", timedelta(days=3)),
    "7": ("Past week", timedelta(days=7)),
    "30": ("Past month", timedelta(days=30)),
}


@bp.route("/jobs")
@login_required
def jobs():
    search = request.args.get("search", "").strip()[:100]
    domain = request.args.get("domain", "").strip()
    if domain not in DOMAINS:
        domain = ""
    location = request.args.get("location", "").strip()[:100]
    posted = request.args.get("posted", "")
    if posted not in POSTED_WINDOWS:
        posted = ""

    query = Job.query.filter(Job.is_open == 1)

    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Job.title.ilike(pattern),
                                 Job.company.ilike(pattern),
                                 Job.required_skills.ilike(pattern)))
    if domain:
        query = query.filter_by(domain=domain)
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if posted:
        # posted_date is "YYYY-MM-DD" or "YYYY-MM-DD HH:MM"; text in this
        # format sorts the same way as the dates themselves
        cutoff = datetime.now() - POSTED_WINDOWS[posted][1]
        query = query.filter(Job.posted_date >= cutoff.strftime("%Y-%m-%d %H:%M"))

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
        posted=posted,
        posted_windows=POSTED_WINDOWS,
        applied_job_ids={job_id for (job_id,) in db.session.query(Submission.job_id)
                         .filter_by(applicant_id=g.user.id)},
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
    submission = (Submission.query.filter_by(job_id=job.id, applicant_id=g.user.id).first()
                  if job.easy_apply else None)

    return render_template(
        "jobs/job_details.html",
        submission=submission,
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
