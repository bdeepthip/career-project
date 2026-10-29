"""
Easy Apply: apply to a job posted on GAJ in one step. GAJ sends the
employer your profile, your resume PDF and an optional note, and adds the
job to your Dashboard as Applied. When the employer updates your status,
your Dashboard updates and you get a notification.
"""

import json
from datetime import date, datetime, timezone

from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
)

from .auth import login_required
from .extensions import limiter, user_key
from .mailer import send_email
from .models import (
    Education, Experience, Job, JobApplication, Profile, Report, Resume, Skill, Submission, db
)
from .notifications import notify, utc_now
from .resumes import pdf_download, read_pdf_upload
from .validation import clean

bp = Blueprint("apply", __name__)


def easy_apply_job_or_404(job_id):
    job = db.session.get(Job, job_id)
    if job is None or not job.easy_apply:
        abort(404)
    return job


def profile_snapshot(user):
    """Everything the employer sees, frozen at the moment of applying."""
    p = Profile.query.filter_by(user_id=user.id).first()
    return {
        "name": user.name,
        "email": user.email,
        "phone": user.phone or (p.phone if p else None),
        "headline": p.headline if p else None,
        "location": p.location if p else None,
        "experience_level": p.experience_level if p else None,
        "about": p.about if p else None,
        "skills": [s.skill_name for s in Skill.query.filter_by(user_id=user.id).order_by(Skill.skill_name)],
        "education": [{"degree": e.degree, "institution": e.institution, "field": e.field_of_study,
                       "years": " to ".join(y for y in (e.start_year, e.end_year) if y)}
                      for e in Education.query.filter_by(user_id=user.id)],
        "experience": [{"title": x.job_title, "company": x.company, "start": x.start_date,
                        "end": x.end_date, "description": x.description}
                       for x in Experience.query.filter_by(user_id=user.id)
                                                .order_by(Experience.start_date.desc())],
    }


@bp.route("/jobs/<int:job_id>/apply", methods=["GET", "POST"])
@login_required
@limiter.limit("30 per day", methods=["POST"], key_func=user_key)
def easy_apply(job_id):
    job = easy_apply_job_or_404(job_id)
    details = redirect(url_for("jobs.job_details", job_id=job.id))

    if g.user.is_employer:
        flash("Easy Apply is for job seeker accounts.", "error")
        return details
    if not job.is_open:
        flash("This job is closed and no longer takes applications.", "error")
        return details
    if Submission.query.filter_by(job_id=job.id, applicant_id=g.user.id).first():
        flash("You already applied to this job.", "info")
        return details

    saved_resume = Resume.query.filter_by(user_id=g.user.id).first()
    snapshot = profile_snapshot(g.user)

    if request.method == "POST":
        note = clean(request.form, "note", 2000)
        upload = request.files.get("resume")
        if upload is not None and upload.filename:
            filename, data, error = read_pdf_upload(upload)
            if error:
                flash(error, "error")
                return render_template("apply/easy_apply.html", job=job, snapshot=snapshot,
                                       resume=saved_resume, note=note), 400
            if request.form.get("save_resume"):
                if saved_resume is None:
                    saved_resume = Resume(user_id=g.user.id)
                    db.session.add(saved_resume)
                saved_resume.filename, saved_resume.data, saved_resume.size = filename, data, len(data)
                saved_resume.uploaded_at = utc_now()
        elif saved_resume is not None:
            filename, data = saved_resume.filename, saved_resume.data
        else:
            flash("Attach your resume as a PDF to apply.", "error")
            return render_template("apply/easy_apply.html", job=job, snapshot=snapshot,
                                   resume=None, note=note), 400

        tracked = JobApplication(
            user_id=g.user.id, company=job.company, job_title=job.title, location=job.location,
            job_url=url_for("jobs.job_details", job_id=job.id), date_applied=date.today().isoformat(),
            status="Applied", notes="Applied with Easy Apply on GAJ",
        )
        db.session.add(tracked)
        db.session.flush()
        now = utc_now()
        submission = Submission(job_id=job.id, applicant_id=g.user.id, application_id=tracked.id,
                                note=note or None, profile_json=json.dumps(snapshot),
                                resume_filename=filename, resume_data=data, status="New",
                                created_at=now, updated_at=now)
        db.session.add(submission)
        db.session.flush()
        notify(job.posted_by_user_id, "applicant", f"New applicant for {job.title}: {g.user.name}",
               link=url_for("employer.applicant", submission_id=submission.id))
        db.session.commit()

        flash(f"Applied to {job.title} at {job.company}. It's on your Dashboard, and you'll get a "
              "notification when they update your status.", "success")
        return details

    return render_template("apply/easy_apply.html", job=job, snapshot=snapshot, resume=saved_resume)


@bp.route("/jobs/<int:job_id>/withdraw", methods=["POST"])
@login_required
def withdraw(job_id):
    job = easy_apply_job_or_404(job_id)
    submission = Submission.query.filter_by(job_id=job.id, applicant_id=g.user.id).first()
    if submission is None:
        abort(404)
    tracked = db.session.get(JobApplication, submission.application_id) if submission.application_id else None
    if tracked is not None and tracked.user_id == g.user.id:
        tracked.notes = ((tracked.notes or "") + " (withdrawn)").strip()
    db.session.delete(submission)
    notify(job.posted_by_user_id, "applicant", f"{g.user.name} withdrew their application for {job.title}.",
           link=url_for("employer.applicants", job_id=job.id))
    db.session.commit()
    flash("Application withdrawn. The employer no longer sees it.", "success")
    return redirect(url_for("jobs.job_details", job_id=job.id))


@bp.route("/jobs/<int:job_id>/my-resume")
@login_required
def sent_resume(job_id):
    """The applicant can download exactly the resume they sent."""
    submission = Submission.query.filter_by(job_id=job_id, applicant_id=g.user.id).first()
    if submission is None or not submission.resume_data:
        abort(404)
    return pdf_download(submission.resume_filename or "resume.pdf", submission.resume_data)


@bp.route("/jobs/<int:job_id>/report", methods=["POST"])
@login_required
@limiter.limit("10 per day", key_func=user_key)
def report_job(job_id):
    job = easy_apply_job_or_404(job_id)
    reason = clean(request.form, "reason", 1000)
    db.session.add(Report(reporter_id=g.user.id, reported_id=job.posted_by_user_id,
                          reason=f"Job #{job.id} ({job.title}): {reason or '(no reason)'}",
                          created_at=utc_now()))
    db.session.commit()
    contact = current_app.config.get("CONTACT_EMAIL")
    if contact:
        send_email(contact, f"GAJ report: job #{job.id}",
                   f"User #{g.user.id} ({g.user.email}) reported job #{job.id} "
                   f"'{job.title}' at {job.company}, posted by user #{job.posted_by_user_id}.\n\n"
                   f"Reason:\n{reason or '(none given)'}\n")
    flash("Thanks for reporting this job. We'll review it.", "success")
    return redirect(url_for("jobs.job_details", job_id=job.id))
