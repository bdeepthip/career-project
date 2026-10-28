"""
Employer accounts and Easy Apply.
"""

import io
import json

import pytest

from jobtrack.models import Job, JobApplication, Notification, Resume, Submission, User, db

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
EMPLOYER, SEEKER, OTHER = "hr@northwind.com", "deepthi@example.com", "rival@example.com"


def register(client, email, name, kind="seeker", company=""):
    client.post("/logout")
    return client.post("/register", data={"name": name, "email": email, "password": "password123",
                                          "account_type": kind, "company": company})


def login(client, email):
    client.post("/logout")
    client.post("/login", data={"email": email, "password": "password123"})


def pdf(name="Deepthi_Resume.pdf", data=PDF):
    return (io.BytesIO(data), name)


@pytest.fixture
def people(client):
    register(client, EMPLOYER, "Hannah Reyes", "employer", "Northwind Health")
    register(client, SEEKER, "Deepthi Priya Busi")
    register(client, OTHER, "Ravi Kumar")
    return client


def post_job(client, **overrides):
    data = {"title": "Data Engineer I", "company": "Northwind Health", "location": "Philadelphia, PA",
            "domain": "Data Analytics", "experience_level": "Entry Level",
            "required_skills": "Python, SQL, Airflow", "description": "Build pipelines. We sponsor H-1B."}
    data.update(overrides)
    return client.post("/employer/jobs/new", data=data)


def job_id(app, title="Data Engineer I"):
    with app.app_context():
        return Job.query.filter_by(title=title).one().id


def apply(client, jid, note="I keep 50 pipelines healthy.", resume=True):
    data = {"note": note}
    if resume:
        data["resume"] = pdf()
        data["save_resume"] = "1"
    return client.post(f"/jobs/{jid}/apply", data=data, content_type="multipart/form-data")


# ---------- Accounts ----------

def test_employer_signup_needs_a_company(client):
    response = register(client, EMPLOYER, "Hannah Reyes", "employer", "")
    assert response.status_code == 400 and b"company you&#39;re hiring for" in response.data


def test_employer_lands_on_job_posts_with_employer_sidebar(app, people):
    login(people, EMPLOYER)
    response = people.get("/dashboard")
    assert response.headers["Location"].endswith("/employer/jobs")
    page = people.get("/employer/jobs").get_data(as_text=True)
    assert "<span>Post a job</span>" in page and "<span>Match Checker</span>" not in page
    assert "data-screen-meter" not in page


def test_seekers_cannot_use_employer_pages(people):
    login(people, SEEKER)
    assert people.get("/employer/jobs").status_code == 302
    assert post_job(people).status_code == 302


# ---------- Posting ----------

def test_post_job_appears_in_feed_with_easy_apply(app, people):
    login(people, EMPLOYER)
    post_job(people)
    login(people, SEEKER)
    page = people.get("/jobs?posted=1").get_data(as_text=True)   # fresh, so past-24h shows it
    assert "Data Engineer I" in page and 'class="easy-tag"' in page and ">Easy Apply</a>" in page


def test_new_job_notifies_seekers_who_match(app, people):
    login(people, SEEKER)
    people.post("/skills/add", data={"skill_name": "Python, SQL, Airflow"})
    login(people, OTHER)
    people.post("/skills/add", data={"skill_name": "Photoshop"})
    login(people, EMPLOYER)
    post_job(people)
    with app.app_context():
        notes = Notification.query.filter_by(kind="job").all()
        assert [n.user_id for n in notes] == [User.query.filter_by(email=SEEKER).one().id]
        assert "100% match" in notes[0].text


def test_closed_job_leaves_feed_and_refuses_applications(app, people):
    login(people, EMPLOYER)
    post_job(people)
    jid = job_id(app)
    people.post(f"/employer/jobs/{jid}/toggle")
    login(people, SEEKER)
    assert b"Data Engineer I" not in people.get("/jobs").data
    apply(people, jid)
    with app.app_context():
        assert Submission.query.count() == 0


def test_employers_cannot_edit_each_others_jobs(app, people):
    login(people, EMPLOYER)
    post_job(people)
    register(people, "hr@other.com", "Other HR", "employer", "Other Co")
    login(people, "hr@other.com")
    assert people.get(f"/employer/jobs/{job_id(app)}/edit").status_code == 404
    assert people.get(f"/employer/jobs/{job_id(app)}/applicants").status_code == 404


# ---------- Applying ----------

def test_easy_apply_end_to_end(app, people):
    login(people, EMPLOYER)
    post_job(people)
    jid = job_id(app)

    login(people, SEEKER)
    people.post("/profile", data={"headline": "Data Engineer | Python, SQL"})
    people.post("/skills/add", data={"skill_name": "Python, SQL"})
    assert apply(people, jid).status_code == 302

    with app.app_context():
        submission = Submission.query.one()
        tracked = db.session.get(JobApplication, submission.application_id)
        assert tracked.company == "Northwind Health" and tracked.status == "Applied"
        assert json.loads(submission.profile_json)["headline"] == "Data Engineer | Python, SQL"
        assert submission.resume_data == PDF
        assert Resume.query.one().filename == "Deepthi_Resume.pdf"   # saved for next time
        sid = submission.id

    # Employer sees the applicant, the match, and the resume
    login(people, EMPLOYER)
    page = people.get(f"/employer/jobs/{jid}/applicants").get_data(as_text=True)
    assert "Deepthi Priya Busi" in page and "<strong>67%</strong>" in page   # 2 of 3 skills
    resume = people.get(f"/employer/applicants/{sid}/resume")
    assert resume.data == PDF and "attachment" in resume.headers["Content-Disposition"]

    # Moving to Interview updates the seeker's Dashboard and notifies them
    people.post(f"/employer/applicants/{sid}", data={"status": "Interview"})
    login(people, SEEKER)
    with app.app_context():
        assert JobApplication.query.one().status == "Interview"
    assert b"Interview with Northwind Health!" in people.get("/notifications").data
    assert b"Status: <span class=\"status status-interview\">Interview" in people.get(f"/jobs/{jid}").data


def test_apply_needs_a_resume(app, people):
    login(people, EMPLOYER)
    post_job(people)
    login(people, SEEKER)
    response = apply(people, job_id(app), resume=False)
    assert response.status_code == 400 and b"Attach your resume" in response.data


def test_saved_resume_is_used(app, people):
    login(people, EMPLOYER)
    post_job(people)
    login(people, SEEKER)
    people.post("/profile/resume", data={"resume": pdf("Saved.pdf")}, content_type="multipart/form-data")
    apply(people, job_id(app), resume=False)
    with app.app_context():
        assert Submission.query.one().resume_filename == "Saved.pdf"


def test_only_real_pdfs_are_accepted(app, people):
    login(people, SEEKER)
    response = people.post("/profile/resume", data={"resume": pdf("evil.pdf", b"<html><script>")},
                           content_type="multipart/form-data", follow_redirects=True)
    assert b"isn&#39;t a PDF" in response.data
    with app.app_context():
        assert Resume.query.count() == 0


def test_resume_over_5_mb_is_refused_politely(app, people):
    login(people, SEEKER)
    big = PDF + b"0" * (5 * 1024 * 1024)
    response = people.post("/profile/resume", data={"resume": pdf("big.pdf", big)},
                           content_type="multipart/form-data", follow_redirects=True)
    assert response.status_code == 200 and b"over 5 MB" in response.data


def test_apply_once_only(app, people):
    login(people, EMPLOYER)
    post_job(people)
    login(people, SEEKER)
    apply(people, job_id(app))
    apply(people, job_id(app))
    with app.app_context():
        assert Submission.query.count() == 1


def test_employers_cannot_easy_apply(app, people):
    login(people, EMPLOYER)
    post_job(people)
    apply(people, job_id(app))
    with app.app_context():
        assert Submission.query.count() == 0


def test_sample_jobs_have_no_easy_apply(people):
    login(people, SEEKER)
    assert people.get("/jobs/1/apply").status_code == 404


def test_withdraw(app, people):
    login(people, EMPLOYER)
    post_job(people)
    jid = job_id(app)
    login(people, SEEKER)
    apply(people, jid)
    people.post(f"/jobs/{jid}/withdraw")
    with app.app_context():
        assert Submission.query.count() == 0
        assert "(withdrawn)" in JobApplication.query.one().notes


# ---------- Privacy ----------

def test_applicants_are_private_to_the_hiring_employer(app, people):
    login(people, EMPLOYER)
    post_job(people)
    login(people, SEEKER)
    apply(people, job_id(app))
    with app.app_context():
        sid = Submission.query.one().id
    register(people, "hr@other.com", "Other HR", "employer", "Other Co")
    login(people, "hr@other.com")
    assert people.get(f"/employer/applicants/{sid}").status_code == 404
    assert people.get(f"/employer/applicants/{sid}/resume").status_code == 404
    login(people, OTHER)
    assert people.get(f"/jobs/{job_id(app)}/my-resume").status_code == 404


def test_report_a_job(app, people):
    from jobtrack import mailer
    login(people, EMPLOYER)
    post_job(people, title="Send us $50 for training")
    login(people, SEEKER)
    mailer.outbox.clear()
    people.post(f"/jobs/{job_id(app, 'Send us $50 for training')}/report", data={"reason": "asks for money"})
    assert "asks for money" in mailer.outbox[0].get_content()
    mailer.outbox.clear()


def test_deleting_employer_removes_jobs_and_applications(app, people):
    login(people, EMPLOYER)
    post_job(people)
    login(people, SEEKER)
    apply(people, job_id(app))
    login(people, EMPLOYER)
    people.post("/account/delete", data={"password": "password123"})
    with app.app_context():
        assert Job.query.filter(Job.posted_by_user_id.isnot(None)).count() == 0
        assert Submission.query.count() == 0
        assert JobApplication.query.count() == 1   # the seeker's own tracker row stays theirs


def test_deleting_seeker_removes_their_applications(app, people):
    login(people, EMPLOYER)
    post_job(people)
    login(people, SEEKER)
    apply(people, job_id(app))
    people.post("/account/delete", data={"password": "password123"})
    with app.app_context():
        assert Submission.query.count() == 0 and Resume.query.count() == 0


def test_export_includes_easy_apply_and_posts(app, people):
    login(people, EMPLOYER)
    post_job(people)
    assert people.get("/account/export").get_json()["job_posts"][0]["title"] == "Data Engineer I"
    login(people, SEEKER)
    apply(people, job_id(app))
    data = people.get("/account/export").get_json()
    assert data["easy_apply_applications"][0]["company"] == "Northwind Health"
    assert data["resume"]["filename"] == "Deepthi_Resume.pdf"
