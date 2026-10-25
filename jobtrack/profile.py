"""
Professional profile: details, skills, education, experience.
"""

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .auth import login_required
from .db import get_db
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
    db = get_db()
    user_id = g.user["id"]

    if request.method == "POST":
        data = {field: clean(request.form, field, 2000 if field == "about" else 150)
                for field in PROFILE_FIELDS}
        if data["domain"] not in DOMAINS:
            data["domain"] = ""
        if data["experience_level"] not in EXPERIENCE_LEVELS:
            data["experience_level"] = ""

        # Insert the profile, or update it if one already exists
        db.execute(
            """
            INSERT INTO profiles
            (user_id, headline, phone, location, domain, target_role,
             experience_level, preferred_location, about)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                headline = excluded.headline,
                phone = excluded.phone,
                location = excluded.location,
                domain = excluded.domain,
                target_role = excluded.target_role,
                experience_level = excluded.experience_level,
                preferred_location = excluded.preferred_location,
                about = excluded.about
            """,
            (user_id, *[data[f] for f in PROFILE_FIELDS]),
        )
        db.commit()

        flash("Profile saved.", "success")
        return redirect(url_for("profile.profile"))

    profile_data = db.execute(
        "SELECT * FROM profiles WHERE user_id = ?", (user_id,)
    ).fetchone()
    skills = db.execute(
        "SELECT * FROM skills WHERE user_id = ? ORDER BY skill_name COLLATE NOCASE",
        (user_id,),
    ).fetchall()
    education = db.execute(
        "SELECT * FROM education WHERE user_id = ? ORDER BY end_year DESC",
        (user_id,),
    ).fetchall()
    experience = db.execute(
        "SELECT * FROM experience WHERE user_id = ? ORDER BY start_date DESC",
        (user_id,),
    ).fetchall()

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
    names = [s.strip()[:60] for s in clean(request.form, "skill_name", 500).split(",")]
    names = [s for s in names if s]

    db = get_db()
    added = 0
    for name in names:
        exists = db.execute(
            "SELECT 1 FROM skills WHERE user_id = ? AND LOWER(skill_name) = LOWER(?)",
            (g.user["id"], name),
        ).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO skills (user_id, skill_name) VALUES (?, ?)",
                (g.user["id"], name),
            )
            added += 1
    db.commit()

    if added:
        flash(f"Added {added} skill{'s' if added != 1 else ''}.", "success")
    return redirect(url_for("profile.profile") + "#skills")


@bp.route("/skills/delete/<int:skill_id>", methods=["POST"])
@login_required
def delete_skill(skill_id):
    db = get_db()
    db.execute("DELETE FROM skills WHERE id = ? AND user_id = ?", (skill_id, g.user["id"]))
    db.commit()
    return redirect(url_for("profile.profile") + "#skills")


@bp.route("/education/add", methods=["POST"])
@login_required
def add_education():
    institution = clean(request.form, "institution", 150)
    degree = clean(request.form, "degree", 150)

    if not institution or not degree:
        flash("Institution and degree are required.", "error")
        return redirect(url_for("profile.profile") + "#education")

    db = get_db()
    db.execute(
        """
        INSERT INTO education
        (user_id, institution, degree, field_of_study, start_year, end_year)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (g.user["id"], institution, degree,
         clean(request.form, "field_of_study", 150),
         clean(request.form, "start_year", 4),
         clean(request.form, "end_year", 4)),
    )
    db.commit()
    flash("Education added.", "success")
    return redirect(url_for("profile.profile") + "#education")


@bp.route("/education/delete/<int:education_id>", methods=["POST"])
@login_required
def delete_education(education_id):
    db = get_db()
    db.execute("DELETE FROM education WHERE id = ? AND user_id = ?",
               (education_id, g.user["id"]))
    db.commit()
    return redirect(url_for("profile.profile") + "#education")


@bp.route("/experience/add", methods=["POST"])
@login_required
def add_experience():
    company = clean(request.form, "company", 150)
    job_title = clean(request.form, "job_title", 150)

    if not company or not job_title:
        flash("Company and job title are required.", "error")
        return redirect(url_for("profile.profile") + "#experience")

    db = get_db()
    db.execute(
        """
        INSERT INTO experience
        (user_id, company, job_title, location, start_date, end_date, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (g.user["id"], company, job_title,
         clean(request.form, "location", 150),
         clean(request.form, "start_date", 7),
         clean(request.form, "end_date", 7),
         clean(request.form, "description", 3000)),
    )
    db.commit()
    flash("Experience added.", "success")
    return redirect(url_for("profile.profile") + "#experience")


@bp.route("/experience/delete/<int:experience_id>", methods=["POST"])
@login_required
def delete_experience(experience_id):
    db = get_db()
    db.execute("DELETE FROM experience WHERE id = ? AND user_id = ?",
               (experience_id, g.user["id"]))
    db.commit()
    return redirect(url_for("profile.profile") + "#experience")
