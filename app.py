from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3
import os

from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv


# ============================================================
# APPLICATION SETUP
# ============================================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("SECRET_KEY is not configured")


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template("index.html")


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        # Basic validation
        if not name or not email or not password:
            return "All fields are required."

        if len(password) < 6:
            return "Password must be at least 6 characters."

        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        # Check duplicate email
        cursor.execute(
            """
            SELECT id FROM users
            WHERE email = ?
            """,
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            connection.close()

            return "An account with this email already exists."

        # Hash password
        hashed_password = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO users
            (name, email, password)
            VALUES (?, ?, ?)
            """,
            (name, email, hashed_password)
        )

        connection.commit()
        connection.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()
        password = request.form["password"]

        connection = sqlite3.connect("database.db")
        connection.row_factory = sqlite3.Row

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT * FROM users
            WHERE email = ?
            """,
            (email,)
        )

        user = cursor.fetchone()

        connection.close()

        # Check user and password
        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("dashboard"))

        return "Invalid email or password"

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    search = request.args.get(
        "search",
        ""
    ).strip()

    status_filter = request.args.get(
        "status",
        ""
    ).strip()

    connection = sqlite3.connect("database.db")

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()


    # --------------------------------------------------------
    # GET APPLICATIONS
    # --------------------------------------------------------

    query = """
        SELECT *
        FROM job_applications
        WHERE user_id = ?
    """

    parameters = [session["user_id"]]


    # Search company/job title
    if search:

        query += """
            AND (
                company LIKE ?
                OR job_title LIKE ?
            )
        """

        search_value = f"%{search}%"

        parameters.append(search_value)
        parameters.append(search_value)


    # Filter by status
    if status_filter:

        query += """
            AND status = ?
        """

        parameters.append(status_filter)


    query += """
        ORDER BY id DESC
    """


    cursor.execute(
        query,
        parameters
    )

    applications = cursor.fetchall()


    # --------------------------------------------------------
    # DASHBOARD STATISTICS
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM job_applications
        WHERE user_id = ?
        """,
        (session["user_id"],)
    )

    total = cursor.fetchone()[0]


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM job_applications
        WHERE user_id = ?
        AND status = 'Applied'
        """,
        (session["user_id"],)
    )

    applied = cursor.fetchone()[0]


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM job_applications
        WHERE user_id = ?
        AND status = 'Interview'
        """,
        (session["user_id"],)
    )

    interviews = cursor.fetchone()[0]


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM job_applications
        WHERE user_id = ?
        AND status = 'Offer'
        """,
        (session["user_id"],)
    )

    offers = cursor.fetchone()[0]


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM job_applications
        WHERE user_id = ?
        AND status = 'Rejected'
        """,
        (session["user_id"],)
    )

    rejected = cursor.fetchone()[0]


    connection.close()


    return render_template(
        "dashboard.html",

        user_name=session["user_name"],

        applications=applications,

        total=total,
        applied=applied,
        interviews=interviews,
        offers=offers,
        rejected=rejected,

        search=search,
        status_filter=status_filter
    )


# ============================================================
# ADD APPLICATION
# ============================================================

@app.route(
    "/applications/add",
    methods=["GET", "POST"]
)
def add_application():

    if "user_id" not in session:
        return redirect(url_for("login"))


    if request.method == "POST":

        company = request.form["company"].strip()

        job_title = request.form[
            "job_title"
        ].strip()

        location = request.form[
            "location"
        ].strip()

        job_url = request.form[
            "job_url"
        ].strip()

        date_applied = request.form[
            "date_applied"
        ]

        status = request.form[
            "status"
        ]

        notes = request.form[
            "notes"
        ].strip()


        connection = sqlite3.connect(
            "database.db"
        )

        cursor = connection.cursor()


        cursor.execute(
            """
            INSERT INTO job_applications
            (
                user_id,
                company,
                job_title,
                location,
                job_url,
                date_applied,
                status,
                notes
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                company,
                job_title,
                location,
                job_url,
                date_applied,
                status,
                notes
            )
        )


        connection.commit()
        connection.close()


        return redirect(
            url_for("dashboard")
        )


    return render_template(
        "add_application.html"
    )


# ============================================================
# EDIT APPLICATION
# ============================================================

@app.route(
    "/applications/edit/<int:application_id>",
    methods=["GET", "POST"]
)
def edit_application(application_id):

    if "user_id" not in session:
        return redirect(url_for("login"))


    connection = sqlite3.connect(
        "database.db"
    )

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()


    # Only get application owned by logged-in user
    cursor.execute(
        """
        SELECT *
        FROM job_applications

        WHERE id = ?
        AND user_id = ?
        """,
        (
            application_id,
            session["user_id"]
        )
    )


    application = cursor.fetchone()


    if application is None:

        connection.close()

        return "Application not found", 404


    if request.method == "POST":

        company = request.form[
            "company"
        ].strip()

        job_title = request.form[
            "job_title"
        ].strip()

        location = request.form[
            "location"
        ].strip()

        job_url = request.form[
            "job_url"
        ].strip()

        date_applied = request.form[
            "date_applied"
        ]

        status = request.form[
            "status"
        ]

        notes = request.form[
            "notes"
        ].strip()


        cursor.execute(
            """
            UPDATE job_applications

            SET company = ?,
                job_title = ?,
                location = ?,
                job_url = ?,
                date_applied = ?,
                status = ?,
                notes = ?

            WHERE id = ?
            AND user_id = ?
            """,
            (
                company,
                job_title,
                location,
                job_url,
                date_applied,
                status,
                notes,

                application_id,
                session["user_id"]
            )
        )


        connection.commit()
        connection.close()


        return redirect(
            url_for("dashboard")
        )


    connection.close()


    return render_template(
        "edit_application.html",
        application=application
    )


# ============================================================
# DELETE APPLICATION
# ============================================================

@app.route(
    "/applications/delete/<int:application_id>",
    methods=["POST"]
)
def delete_application(application_id):

    if "user_id" not in session:
        return redirect(url_for("login"))


    connection = sqlite3.connect(
        "database.db"
    )

    cursor = connection.cursor()


    cursor.execute(
        """
        DELETE FROM job_applications

        WHERE id = ?
        AND user_id = ?
        """,
        (
            application_id,
            session["user_id"]
        )
    )


    connection.commit()
    connection.close()


    return redirect(
        url_for("dashboard")
    )


# ============================================================
# PROFESSIONAL PROFILE
# ============================================================

@app.route(
    "/profile",
    methods=["GET", "POST"]
)
def profile():

    if "user_id" not in session:
        return redirect(url_for("login"))


    user_id = session["user_id"]


    connection = sqlite3.connect(
        "database.db"
    )

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()


    # --------------------------------------------------------
    # SAVE / UPDATE PROFILE
    # --------------------------------------------------------

    if request.method == "POST":

        headline = request.form[
            "headline"
        ].strip()

        phone = request.form[
            "phone"
        ].strip()

        location = request.form[
            "location"
        ].strip()

        domain = request.form[
            "domain"
        ].strip()

        target_role = request.form[
            "target_role"
        ].strip()

        experience_level = request.form[
            "experience_level"
        ].strip()

        preferred_location = request.form[
            "preferred_location"
        ].strip()

        about = request.form[
            "about"
        ].strip()


        cursor.execute(
            """
            SELECT id
            FROM profiles
            WHERE user_id = ?
            """,
            (user_id,)
        )


        existing_profile = cursor.fetchone()


        # UPDATE existing profile
        if existing_profile:

            cursor.execute(
                """
                UPDATE profiles

                SET headline = ?,
                    phone = ?,
                    location = ?,
                    domain = ?,
                    target_role = ?,
                    experience_level = ?,
                    preferred_location = ?,
                    about = ?

                WHERE user_id = ?
                """,
                (
                    headline,
                    phone,
                    location,
                    domain,
                    target_role,
                    experience_level,
                    preferred_location,
                    about,
                    user_id
                )
            )


        # CREATE new profile
        else:

            cursor.execute(
                """
                INSERT INTO profiles
                (
                    user_id,
                    headline,
                    phone,
                    location,
                    domain,
                    target_role,
                    experience_level,
                    preferred_location,
                    about
                )

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    headline,
                    phone,
                    location,
                    domain,
                    target_role,
                    experience_level,
                    preferred_location,
                    about
                )
            )


        connection.commit()
        connection.close()


        return redirect(
            url_for("profile")
        )


    # --------------------------------------------------------
    # GET PROFILE
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT *
        FROM profiles
        WHERE user_id = ?
        """,
        (user_id,)
    )

    profile_data = cursor.fetchone()


    # --------------------------------------------------------
    # GET SKILLS
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT *
        FROM skills

        WHERE user_id = ?

        ORDER BY skill_name
        """,
        (user_id,)
    )

    skills = cursor.fetchall()


    # --------------------------------------------------------
    # GET EDUCATION
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT *
        FROM education

        WHERE user_id = ?

        ORDER BY end_year DESC
        """,
        (user_id,)
    )

    education = cursor.fetchall()


    # --------------------------------------------------------
    # GET EXPERIENCE
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT *
        FROM experience

        WHERE user_id = ?

        ORDER BY start_date DESC
        """,
        (user_id,)
    )

    experience = cursor.fetchall()


    connection.close()


    return render_template(
        "profile.html",

        profile=profile_data,

        skills=skills,

        education=education,

        experience=experience,

        user_name=session["user_name"]
    )


# ============================================================
# ADD SKILL
# ============================================================

@app.route(
    "/skills/add",
    methods=["POST"]
)
def add_skill():

    if "user_id" not in session:
        return redirect(url_for("login"))


    skill_name = request.form[
        "skill_name"
    ].strip()


    if skill_name:

        connection = sqlite3.connect(
            "database.db"
        )

        cursor = connection.cursor()


        # Prevent duplicate skills
        cursor.execute(
            """
            SELECT id
            FROM skills

            WHERE user_id = ?
            AND LOWER(skill_name) = LOWER(?)
            """,
            (
                session["user_id"],
                skill_name
            )
        )


        existing_skill = cursor.fetchone()


        if not existing_skill:

            cursor.execute(
                """
                INSERT INTO skills
                (
                    user_id,
                    skill_name
                )

                VALUES (?, ?)
                """,
                (
                    session["user_id"],
                    skill_name
                )
            )


            connection.commit()


        connection.close()


    return redirect(
        url_for("profile")
    )


# ============================================================
# DELETE SKILL
# ============================================================

@app.route(
    "/skills/delete/<int:skill_id>",
    methods=["POST"]
)
def delete_skill(skill_id):

    if "user_id" not in session:
        return redirect(url_for("login"))


    connection = sqlite3.connect(
        "database.db"
    )

    cursor = connection.cursor()


    cursor.execute(
        """
        DELETE FROM skills

        WHERE id = ?
        AND user_id = ?
        """,
        (
            skill_id,
            session["user_id"]
        )
    )


    connection.commit()
    connection.close()


    return redirect(
        url_for("profile")
    )


# ============================================================
# ADD EDUCATION
# ============================================================

@app.route(
    "/education/add",
    methods=["POST"]
)
def add_education():

    if "user_id" not in session:
        return redirect(url_for("login"))


    institution = request.form[
        "institution"
    ].strip()

    degree = request.form[
        "degree"
    ].strip()

    field_of_study = request.form[
        "field_of_study"
    ].strip()

    start_year = request.form[
        "start_year"
    ].strip()

    end_year = request.form[
        "end_year"
    ].strip()


    if institution and degree:

        connection = sqlite3.connect(
            "database.db"
        )

        cursor = connection.cursor()


        cursor.execute(
            """
            INSERT INTO education
            (
                user_id,
                institution,
                degree,
                field_of_study,
                start_year,
                end_year
            )

            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                institution,
                degree,
                field_of_study,
                start_year,
                end_year
            )
        )


        connection.commit()
        connection.close()


    return redirect(
        url_for("profile")
    )


# ============================================================
# DELETE EDUCATION
# ============================================================

@app.route(
    "/education/delete/<int:education_id>",
    methods=["POST"]
)
def delete_education(education_id):

    if "user_id" not in session:
        return redirect(url_for("login"))


    connection = sqlite3.connect(
        "database.db"
    )

    cursor = connection.cursor()


    cursor.execute(
        """
        DELETE FROM education

        WHERE id = ?
        AND user_id = ?
        """,
        (
            education_id,
            session["user_id"]
        )
    )


    connection.commit()
    connection.close()


    return redirect(
        url_for("profile")
    )


# ============================================================
# ADD EXPERIENCE
# ============================================================

@app.route(
    "/experience/add",
    methods=["POST"]
)
def add_experience():

    if "user_id" not in session:
        return redirect(url_for("login"))


    company = request.form[
        "company"
    ].strip()

    job_title = request.form[
        "job_title"
    ].strip()

    location = request.form[
        "location"
    ].strip()

    start_date = request.form[
        "start_date"
    ].strip()

    end_date = request.form[
        "end_date"
    ].strip()

    description = request.form[
        "description"
    ].strip()


    if company and job_title:

        connection = sqlite3.connect(
            "database.db"
        )

        cursor = connection.cursor()


        cursor.execute(
            """
            INSERT INTO experience
            (
                user_id,
                company,
                job_title,
                location,
                start_date,
                end_date,
                description
            )

            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                company,
                job_title,
                location,
                start_date,
                end_date,
                description
            )
        )


        connection.commit()
        connection.close()


    return redirect(
        url_for("profile")
    )


# ============================================================
# DELETE EXPERIENCE
# ============================================================

@app.route(
    "/experience/delete/<int:experience_id>",
    methods=["POST"]
)
def delete_experience(experience_id):

    if "user_id" not in session:
        return redirect(url_for("login"))


    connection = sqlite3.connect(
        "database.db"
    )

    cursor = connection.cursor()


    cursor.execute(
        """
        DELETE FROM experience

        WHERE id = ?
        AND user_id = ?
        """,
        (
            experience_id,
            session["user_id"]
        )
    )


    connection.commit()
    connection.close()


    return redirect(
        url_for("profile")
    )
# ============================================================
# MATCH SCORE HELPERS
# ============================================================

def parse_skills(skills_text):
    """Turn 'Python, Flask, SQL' into {'python': 'Python', ...}.
    Lowercase keys make matching case-insensitive;
    values keep the original spelling for display."""

    skills = {}

    for skill in (skills_text or "").split(","):
        skill = skill.strip()
        if skill:
            skills[skill.lower()] = skill

    return skills


def calculate_match(cursor, user_id, required_skills_text):
    """Compare the user's profile skills to a job's required skills.
    Returns (score, matched_skills, missing_skills)."""

    cursor.execute(
        "SELECT skill_name FROM skills WHERE user_id = ?",
        (user_id,)
    )

    user_skills = {
        row[0].strip().lower()
        for row in cursor.fetchall()
    }

    required = parse_skills(required_skills_text)

    if not required:
        return 0, [], []

    matched = [
        original for lower, original in required.items()
        if lower in user_skills
    ]

    missing = [
        original for lower, original in required.items()
        if lower not in user_skills
    ]

    score = round(len(matched) / len(required) * 100)

    return score, matched, missing

# ============================================================
# JOB FEED
# ============================================================

@app.route("/jobs")
def jobs():

    if "user_id" not in session:
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()
    domain = request.args.get("domain", "").strip()
    location = request.args.get("location", "").strip()

    connection = sqlite3.connect("database.db")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    query = """
        SELECT *
        FROM jobs
        WHERE 1 = 1
    """

    parameters = []

    # Search job title or company
    if search:

        query += """
            AND (
                title LIKE ?
                OR company LIKE ?
                OR required_skills LIKE ?
            )
        """

        search_value = f"%{search}%"

        parameters.extend([
            search_value,
            search_value,
            search_value
        ])

    # Filter by domain
    if domain:

        query += """
            AND domain = ?
        """

        parameters.append(domain)

    # Filter by location
    if location:

        query += """
            AND location LIKE ?
        """

        parameters.append(f"%{location}%")

    query += """
        ORDER BY posted_date DESC
    """

    cursor.execute(query, parameters)

    jobs_rows = cursor.fetchall()

    # Add a match score to each job
    jobs_data = []

    for job in jobs_rows:
        score, _, _ = calculate_match(
            cursor,
            session["user_id"],
            job["required_skills"]
        )

        job_dict = dict(job)
        job_dict["match_score"] = score
        jobs_data.append(job_dict)

    connection.close()

    return render_template(
        "jobs.html",
        jobs=jobs_data,
        search=search,
        domain=domain,
        location=location
    )

# ============================================================
# JOB DETAILS
# ============================================================

@app.route("/jobs/<int:job_id>")
def job_details(job_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = sqlite3.connect("database.db")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM jobs WHERE id = ?",
        (job_id,)
    )

    job = cursor.fetchone()

    if job is None:
        connection.close()
        return "Job not found", 404

    match_score, matched, missing = calculate_match(
        cursor,
        session["user_id"],
        job["required_skills"]
    )

    # Find learning resources for the missing skills
    resources = {}

    if missing:
        placeholders = ",".join("?" * len(missing))

        cursor.execute(
            f"""
            SELECT *
            FROM learning_resources
            WHERE LOWER(skill_name) IN ({placeholders})
            """,
            [skill.lower() for skill in missing]
        )

        for row in cursor.fetchall():
            resources[row["skill_name"].lower()] = row

    connection.close()

    learning_plan = [
        {
            "skill": skill,
            "resource": resources.get(skill.lower())
        }
        for skill in missing
    ]

    total_hours = sum(
        item["resource"]["estimated_hours"] or 0
        for item in learning_plan
        if item["resource"]
    )

    return render_template(
        "job_details.html",
        job=job,
        match_score=match_score,
        matched=matched,
        missing=missing,
        learning_plan=learning_plan,
        total_hours=total_hours
    )

# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":
    app.run(
        debug=True,
        port=5001
    )