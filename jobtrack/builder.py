"""
Resume builder pages: build resumes from the profile, tailor a copy for
each job with a keyword-match score, and download them as PDFs.
"""

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)

from . import resume_content as rc
from .auth import login_required
from .extensions import limiter, user_key
from .models import Job, ResumeVersion, db
from .notifications import utc_now
from .resumes import pdf_download
from .validation import clean

bp = Blueprint("builder", __name__)

MOST_VERSIONS = 30


def seekers_only():
    if g.user.is_employer:
        flash("The resume builder is for job seeker accounts.", "error")
        return redirect(url_for("employer.posts"))
    return None


def get_version(version_id):
    """One of the logged-in user's resumes; anyone else's is a 404."""
    version = ResumeVersion.query.filter_by(id=version_id, user_id=g.user.id).first()
    if version is None:
        abort(404)
    return version


def version_score(version, content=None):
    job_text, required = rc.job_text_for(version)
    return rc.score(content or rc.load(version.content_json), job_text, required)


@bp.route("/resumes")
@login_required
def resumes():
    blocked = seekers_only()
    if blocked:
        return blocked
    versions = (ResumeVersion.query.filter_by(user_id=g.user.id)
                .order_by(ResumeVersion.updated_at.desc()).all())
    scores = {v.id: version_score(v) for v in versions}
    return render_template("builder/resumes.html", versions=versions, scores=scores)


@bp.route("/resumes/new", methods=["POST"])
@login_required
def new_resume():
    """Start a resume from the profile, or from a copy of another
    resume. With job_id it is tailored for that Roleflow job."""
    blocked = seekers_only()
    if blocked:
        return blocked
    if ResumeVersion.query.filter_by(user_id=g.user.id).count() >= MOST_VERSIONS:
        flash(f"You can keep up to {MOST_VERSIONS} resumes. Delete one you no longer need.", "error")
        return redirect(url_for("builder.resumes"))

    job = None
    job_id = request.form.get("job_id", type=int)
    if job_id:
        job = db.session.get(Job, job_id)
        if job is None:
            abort(404)

    source_id = request.form.get("from", type=int)
    if source_id:
        source = get_version(source_id)
        content = rc.load(source.content_json)
    else:
        # Start from the newest resume if there is one: it's usually the
        # most polished, and tailoring is about small changes
        latest = (ResumeVersion.query.filter_by(user_id=g.user.id)
                  .order_by(ResumeVersion.updated_at.desc()).first())
        content = rc.load(latest.content_json) if (latest and job) else rc.from_profile(g.user)

    name = clean(request.form, "name", 80)
    if not name:
        name = f"{job.company}: {job.title}"[:80] if job else "My resume"

    now = utc_now()
    version = ResumeVersion(user_id=g.user.id, name=name, job_id=job.id if job else None,
                            content_json=rc.dump(content), created_at=now, updated_at=now)
    db.session.add(version)
    db.session.commit()
    return redirect(url_for("builder.edit_resume", version_id=version.id))


@bp.route("/resumes/<int:version_id>", methods=["GET", "POST"])
@login_required
def edit_resume(version_id):
    blocked = seekers_only()
    if blocked:
        return blocked
    version = get_version(version_id)

    if request.method == "POST":
        content = rc.from_form(request.form)
        version.name = clean(request.form, "version_name", 80) or version.name
        if version.job_id is None:
            version.target_text = clean(request.form, "target_text", 20000) or None
        version.content_json = rc.dump(content)
        version.updated_at = utc_now()
        db.session.commit()
        flash("Saved.", "success")
        anchor = request.form.get("after_save", "")
        return redirect(url_for("builder.edit_resume", version_id=version.id)
                        + ("#match" if anchor == "match" else ""))

    content = rc.load(version.content_json)
    return render_template("builder/editor.html", version=version, content=content,
                           result=version_score(version, content), sections=rc.SECTIONS)


@bp.route("/resumes/<int:version_id>/pdf")
@login_required
@limiter.limit("60 per hour", key_func=user_key)
def resume_pdf(version_id):
    version = get_version(version_id)
    content = rc.load(version.content_json)
    return pdf_download(rc.pdf_filename(content), rc.to_pdf(content))


@bp.route("/resumes/<int:version_id>/copy", methods=["POST"])
@login_required
def copy_resume(version_id):
    version = get_version(version_id)
    if ResumeVersion.query.filter_by(user_id=g.user.id).count() >= MOST_VERSIONS:
        flash(f"You can keep up to {MOST_VERSIONS} resumes. Delete one you no longer need.", "error")
        return redirect(url_for("builder.resumes"))
    now = utc_now()
    copy = ResumeVersion(user_id=g.user.id, name=f"Copy of {version.name}"[:80],
                         content_json=version.content_json, created_at=now, updated_at=now)
    db.session.add(copy)
    db.session.commit()
    flash(f"Made a copy of {version.name}.", "success")
    return redirect(url_for("builder.edit_resume", version_id=copy.id))


@bp.route("/resumes/<int:version_id>/delete", methods=["POST"])
@login_required
def delete_resume(version_id):
    version = get_version(version_id)
    name = version.name
    db.session.delete(version)
    db.session.commit()
    flash(f"Deleted {name}.", "success")
    return redirect(url_for("builder.resumes"))
