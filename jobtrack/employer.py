"""
Employer accounts: post jobs on GAJ and review the people who Easy Apply.

Each status change an employer makes (Reviewing, Interview, Offer,
Rejected) is mirrored on the applicant's own Dashboard and sent to them
as a notification, so applicants are never left guessing.
"""

import functools
import json
from datetime import datetime

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)
from sqlalchemy import func

from .auth import login_required
from .extensions import limiter, user_key
from .matching import calculate_match
from .models import JobApplication, Job, Skill, Submission, User, db
from .notifications import notify, utc_now
from .profile import DOMAINS, EXPERIENCE_LEVELS
from .resumes import pdf_download
from .validation import clean

bp = Blueprint("employer", __name__)

SUBMISSION_STATUSES = ["New", "Reviewing", "Interview", "Offer", "Rejected"]
# What the applicant's Dashboard shows for each employer status
TRACKER_STATUS = {"New": "Applied", "Reviewing": "Applied", "Interview": "Interview",
                  "Offer": "Offer", "Rejected": "Rejected"}
NOTIFY_ABOUT_NEW_JOB_AT = 70   # % match needed to tell a seeker about a new job


def employer_required(view):
    @functools.wraps(view)
    @login_required
    def wrapped(**kwargs):
        if not g.user.is_employer:
            flash("That page is for employer accounts.", "error")
            return redirect(url_for("applications.dashboard"))
        return view(**kwargs)
    return wrapped


def own_job_or_404(job_id):
    job = Job.query.filter_by(id=job_id, posted_by_user_id=g.user.id).first()
    if job is None:
        abort(404)
    return job


def own_submission_or_404(submission_id):
    submission = (Submission.query.join(Job, Submission.job_id == Job.id)
                  .filter(Submission.id == submission_id, Job.posted_by_user_id == g.user.id)
                  .first())
    if submission is None:
        abort(404)
    return submission


# ---------- Job posts ----------

@bp.route("/employer/jobs")
@employer_required
def posts():
    jobs = (Job.query.filter_by(posted_by_user_id=g.user.id)
            .order_by(Job.is_open.desc(), Job.posted_date.desc()).all())
    counts = dict(db.session.query(Submission.job_id, func.count())
                  .filter(Submission.job_id.in_([j.id for j in jobs] or [0]))
                  .group_by(Submission.job_id))
    new_counts = dict(db.session.query(Submission.job_id, func.count())
                      .filter(Submission.job_id.in_([j.id for j in jobs] or [0]),
                              Submission.status == "New")
                      .group_by(Submission.job_id))
    return render_template("employer/posts.html", jobs=jobs, counts=counts, new_counts=new_counts)


def read_job_form():
    data = {
        "title": clean(request.form, "title", 120),
        "company": clean(request.form, "company", 120) or (g.user.company or ""),
        "location": clean(request.form, "location", 120),
        "domain": clean(request.form, "domain", 60),
        "experience_level": clean(request.form, "experience_level", 40),
        "required_skills": ", ".join(s.strip()[:60] for s in clean(request.form, "required_skills", 600).split(",") if s.strip()),
        "description": clean(request.form, "description", 8000),
    }
    if data["domain"] not in DOMAINS:
        data["domain"] = ""
    if data["experience_level"] not in EXPERIENCE_LEVELS:
        data["experience_level"] = ""
    errors = [label for field, label in (("title", "a job title"), ("company", "the company"),
                                         ("location", "a location"), ("description", "a description"))
              if not data[field]]
    return data, (["Add " + ", ".join(errors) + "."] if errors else [])


def tell_matching_seekers(job):
    """Let job seekers whose skills fit this job well know it was posted."""
    skills_by_user = {}
    for user_id, name in (db.session.query(Skill.user_id, Skill.skill_name)
                          .join(User, User.id == Skill.user_id)
                          .filter(User.account_type == "seeker")):
        skills_by_user.setdefault(user_id, set()).add(name.strip().lower())
    told = 0
    for user_id, skills in skills_by_user.items():
        score, _, _ = calculate_match(skills, job.required_skills)
        if score >= NOTIFY_ABOUT_NEW_JOB_AT:
            notify(user_id, "job", f"New on GAJ: {job.title} at {job.company} ({score}% match). "
                                   "You can Easy Apply.",
                   link=url_for("jobs.job_details", job_id=job.id))
            told += 1
            if told >= 500:
                break


@bp.route("/employer/jobs/new", methods=["GET", "POST"])
@employer_required
@limiter.limit("20 per day", methods=["POST"], key_func=user_key)
def new_job():
    if request.method == "POST":
        data, errors = read_job_form()
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("employer/job_form.html", job=data, mode="new",
                                   domains=DOMAINS, levels=EXPERIENCE_LEVELS), 400
        job = Job(**data, posted_by_user_id=g.user.id, is_open=1,
                  posted_date=datetime.now().strftime("%Y-%m-%d %H:%M"))
        db.session.add(job)
        db.session.flush()
        tell_matching_seekers(job)
        db.session.commit()
        flash(f"Posted: {job.title}. Job seekers can Easy Apply now.", "success")
        return redirect(url_for("employer.posts"))

    return render_template("employer/job_form.html", job={"company": g.user.company or ""},
                           mode="new", domains=DOMAINS, levels=EXPERIENCE_LEVELS)


@bp.route("/employer/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@employer_required
def edit_job(job_id):
    job = own_job_or_404(job_id)
    if request.method == "POST":
        data, errors = read_job_form()
        if errors:
            for error in errors:
                flash(error, "error")
            data["id"] = job.id
            return render_template("employer/job_form.html", job=data, mode="edit",
                                   domains=DOMAINS, levels=EXPERIENCE_LEVELS), 400
        for field, value in data.items():
            setattr(job, field, value)
        db.session.commit()
        flash("Job updated.", "success")
        return redirect(url_for("employer.posts"))
    return render_template("employer/job_form.html", job=job, mode="edit",
                           domains=DOMAINS, levels=EXPERIENCE_LEVELS)


@bp.route("/employer/jobs/<int:job_id>/toggle", methods=["POST"])
@employer_required
def toggle_job(job_id):
    job = own_job_or_404(job_id)
    job.is_open = 0 if job.is_open else 1
    db.session.commit()
    flash(f"{job.title} is {'open again' if job.is_open else 'closed: it no longer takes applications'}.",
          "success")
    return redirect(url_for("employer.posts"))


# ---------- Applicants ----------

@bp.route("/employer/jobs/<int:job_id>/applicants")
@employer_required
def applicants(job_id):
    job = own_job_or_404(job_id)
    status_filter = request.args.get("status", "")
    query = Submission.query.filter_by(job_id=job.id)
    if status_filter in SUBMISSION_STATUSES:
        query = query.filter_by(status=status_filter)
    rows = []
    for submission in query.order_by(Submission.created_at.desc()).all():
        profile = json.loads(submission.profile_json)
        score, _, _ = calculate_match({s.lower() for s in profile.get("skills", [])}, job.required_skills)
        rows.append({"submission": submission, "profile": profile, "score": score})
    return render_template("employer/applicants.html", job=job, rows=rows,
                           statuses=SUBMISSION_STATUSES, status_filter=status_filter)


@bp.route("/employer/applicants/<int:submission_id>", methods=["GET", "POST"])
@employer_required
def applicant(submission_id):
    submission = own_submission_or_404(submission_id)
    job = submission.job

    if request.method == "POST":
        status = request.form.get("status")
        if status not in SUBMISSION_STATUSES:
            abort(400)
        if status != submission.status:
            submission.status = status
            submission.updated_at = utc_now()
            tracked = db.session.get(JobApplication, submission.application_id) if submission.application_id else None
            if tracked is not None:
                tracked.status = TRACKER_STATUS[status]
            if status != "New":
                message = {
                    "Reviewing": f"{job.company} is reviewing your application for {job.title}.",
                    "Interview": f"Interview with {job.company}! They moved your {job.title} application forward.",
                    "Offer": f"Offer from {job.company} for {job.title}!",
                    "Rejected": f"{job.company} decided not to move forward with your {job.title} application.",
                }[status]
                notify(submission.applicant_id, "status", message,
                       link=url_for("jobs.job_details", job_id=job.id))
            db.session.commit()
            flash(f"Status set to {status}. The applicant has been notified.", "success")
        return redirect(url_for("employer.applicant", submission_id=submission.id))

    profile = json.loads(submission.profile_json)
    score, matched, missing = calculate_match({s.lower() for s in profile.get("skills", [])},
                                              job.required_skills)
    return render_template("employer/applicant.html", submission=submission, job=job,
                           profile=profile, score=score, matched=matched, missing=missing,
                           statuses=SUBMISSION_STATUSES)


@bp.route("/employer/applicants/<int:submission_id>/resume")
@employer_required
def applicant_resume(submission_id):
    submission = own_submission_or_404(submission_id)
    if not submission.resume_data:
        abort(404)
    return pdf_download(submission.resume_filename or "resume.pdf", submission.resume_data)
