from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3
import os

from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("SECRET_KEY is not configured")


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- REGISTER ----------------

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

        # Check whether email already exists
        cursor.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:
            connection.close()
            return "An account with this email already exists."

        hashed_password = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO users (name, email, password)
            VALUES (?, ?, ?)
            """,
            (name, email, hashed_password)
        )

        connection.commit()
        connection.close()

        return redirect(url_for("login"))

    return render_template("register.html")
# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        connection = sqlite3.connect("database.db")

        # Allows us to access columns using names:
        # user["email"], user["password"], etc.
        connection.row_factory = sqlite3.Row

        cursor = connection.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        )

        user = cursor.fetchone()

        connection.close()

        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("dashboard"))

        return "Invalid email or password"

    return render_template("login.html")


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    # Get search/filter values from URL
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()

    connection = sqlite3.connect("database.db")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    # Start query with logged-in user's applications only
    query = """
        SELECT * FROM job_applications
        WHERE user_id = ?
    """

    parameters = [session["user_id"]]

    # Search by company or job title
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
        query += " AND status = ?"
        parameters.append(status_filter)

    query += " ORDER BY id DESC"

    cursor.execute(query, parameters)

    applications = cursor.fetchall()

    # ---------------- STATISTICS ----------------

    cursor.execute(
        """
        SELECT COUNT(*) FROM job_applications
        WHERE user_id = ?
        """,
        (session["user_id"],)
    )
    total = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*) FROM job_applications
        WHERE user_id = ? AND status = 'Applied'
        """,
        (session["user_id"],)
    )
    applied = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*) FROM job_applications
        WHERE user_id = ? AND status = 'Interview'
        """,
        (session["user_id"],)
    )
    interviews = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*) FROM job_applications
        WHERE user_id = ? AND status = 'Offer'
        """,
        (session["user_id"],)
    )
    offers = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*) FROM job_applications
        WHERE user_id = ? AND status = 'Rejected'
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

# ---------------- ADD APPLICATION ----------------

@app.route("/applications/add", methods=["GET", "POST"])
def add_application():

    # User must be logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        company = request.form["company"]
        job_title = request.form["job_title"]
        location = request.form["location"]
        job_url = request.form["job_url"]
        date_applied = request.form["date_applied"]
        status = request.form["status"]
        notes = request.form["notes"]

        connection = sqlite3.connect("database.db")
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO job_applications
            (user_id, company, job_title, location, job_url,
             date_applied, status, notes)
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

        return redirect(url_for("dashboard"))

    return render_template("add_application.html")

# ---------------- EDIT APPLICATION ----------------

@app.route("/applications/edit/<int:application_id>", methods=["GET", "POST"])
def edit_application(application_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = sqlite3.connect("database.db")
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    # Get only an application belonging to the logged-in user
    cursor.execute(
        """
        SELECT * FROM job_applications
        WHERE id = ? AND user_id = ?
        """,
        (application_id, session["user_id"])
    )

    application = cursor.fetchone()

    if application is None:
        connection.close()
        return "Application not found", 404

    if request.method == "POST":

        company = request.form["company"]
        job_title = request.form["job_title"]
        location = request.form["location"]
        job_url = request.form["job_url"]
        date_applied = request.form["date_applied"]
        status = request.form["status"]
        notes = request.form["notes"]

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

            WHERE id = ? AND user_id = ?
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

        return redirect(url_for("dashboard"))

    connection.close()

    return render_template(
        "edit_application.html",
        application=application
    )

# ---------------- DELETE APPLICATION ----------------

@app.route("/applications/delete/<int:application_id>", methods=["POST"])
def delete_application(application_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM job_applications
        WHERE id = ? AND user_id = ?
        """,
        (application_id, session["user_id"])
    )

    connection.commit()
    connection.close()

    return redirect(url_for("dashboard"))
# ---------------- START APPLICATION ----------------

if __name__ == "__main__":
    app.run(debug=True, port=5001)