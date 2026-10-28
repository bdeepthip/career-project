"""
Professional profile: details, skills, education, experience.
"""

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func

from .auth import login_required
from .models import Education, Experience, Profile, Skill, db
from .validation import clean

bp = Blueprint("profile", __name__)

DOMAINS = [
    "Software Development", "Data Science", "Data Analytics",
    "Cybersecurity", "Cloud / DevOps", "AI / Machine Learning",
]
EXPERIENCE_LEVELS = ["Entry Level", "1-2 Years", "3-5 Years", "5+ Years"]

PROFILE_FIELDS = [
    "headline", "phone", "location", "domain", "target_role",
    "experience_level", "preferred_location", "about",
]


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = g.user.id
    profile_data = Profile.query.filter_by(user_id=user_id).first()

    if request.method == "POST":
        data = {field: clean(request.form, field, 2000 if field == "about" else 150)
                for field in PROFILE_FIELDS}
        if data["domain"] not in DOMAINS:
            data["domain"] = ""
        if data["experience_level"] not in EXPERIENCE_LEVELS:
            data["experience_level"] = ""

        # Update the profile, or create it the first time
        if profile_data is None:
            profile_data = Profile(user_id=user_id)
            db.session.add(profile_data)
        for field, value in data.items():
            setattr(profile_data, field, value)
        db.session.commit()

        flash("Profile saved.", "success")
        return redirect(url_for("profile.profile"))

    skills = (Skill.query.filter_by(user_id=user_id)
              .order_by(func.lower(Skill.skill_name)).all())
    education = (Education.query.filter_by(user_id=user_id)
                 .order_by(Education.end_year.desc()).all())
    experience = (Experience.query.filter_by(user_id=user_id)
                  .order_by(Experience.start_date.desc()).all())

    return render_template(
        "profile/profile.html",
        profile=profile_data,
        skills=skills,
        education=education,
        experience=experience,
        domains=DOMAINS,
        experience_levels=EXPERIENCE_LEVELS,
    )


@bp.route("/skills/add", methods=["POST"])
@login_required
def add_skill():
    # Allow "Python, SQL, Git" in one go
    names = [n.strip()[:60] for n in clean(request.form, "skill_name", 500).split(",")]
    names = [n for n in names if n]

    existing = {name.lower() for (name,) in
                db.session.query(Skill.skill_name).filter_by(user_id=g.user.id)}
    added = 0
    for name in names:
        if name.lower() not in existing:
            db.session.add(Skill(user_id=g.user.id, skill_name=name))
            existing.add(name.lower())
            added += 1
    db.session.commit()

    if added:
        flash(f"Added {added} skill{'s' if added != 1 else ''}.", "success")
    return redirect(url_for("profile.profile") + "#skills")


def _delete_owned(model, row_id):
    """Delete one row only if it belongs to the logged-in user."""
    model.query.filter_by(id=row_id, user_id=g.user.id).delete()
    db.session.commit()


@bp.route("/skills/delete/<int:skill_id>", methods=["POST"])
@login_required
def delete_skill(skill_id):
    _delete_owned(Skill, skill_id)
    return redirect(url_for("profile.profile") + "#skills")


@bp.route("/education/add", methods=["POST"])
@login_required
def add_education():
    institution = clean(request.form, "institution", 150)
    degree = clean(request.form, "degree", 150)

    if not institution or not degree:
        flash("Institution and degree are required.", "error")
        return redirect(url_for("profile.profile") + "#education")

    db.session.add(Education(
        user_id=g.user.id, institution=institution, degree=degree,
        field_of_study=clean(request.form, "field_of_study", 150),
        start_year=clean(request.form, "start_year", 4),
        end_year=clean(request.form, "end_year", 4),
    ))
    db.session.commit()
    flash("Education added.", "success")
    return redirect(url_for("profile.profile") + "#education")


@bp.route("/education/delete/<int:education_id>", methods=["POST"])
@login_required
def delete_education(education_id):
    _delete_owned(Education, education_id)
    return redirect(url_for("profile.profile") + "#education")


@bp.route("/experience/add", methods=["POST"])
@login_required
def add_experience():
    company = clean(request.form, "company", 150)
    job_title = clean(request.form, "job_title", 150)

    if not company or not job_title:
        flash("Company and job title are required.", "error")
        return redirect(url_for("profile.profile") + "#experience")

    db.session.add(Experience(
        user_id=g.user.id, company=company, job_title=job_title,
        location=clean(request.form, "location", 150),
        start_date=clean(request.form, "start_date", 7),
        end_date=clean(request.form, "end_date", 7),
        description=clean(request.form, "description", 3000),
    ))
    db.session.commit()
    flash("Experience added.", "success")
    return redirect(url_for("profile.profile") + "#experience")


@bp.route("/experience/delete/<int:experience_id>", methods=["POST"])
@login_required
def delete_experience(experience_id):
    _delete_owned(Experience, experience_id)
    return redirect(url_for("profile.profile") + "#experience")
