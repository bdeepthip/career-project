"""
The resume builder: drafts from the profile, editing, keyword match,
PDF output, tailoring for a job and sending a built resume.
"""

import io
import json

import pytest
from pypdf import PdfReader

from jobtrack import resume_content as rc
from jobtrack.models import Job, ResumeVersion, Submission, db
from test_easy_apply import EMPLOYER, SEEKER, OTHER, job_id, login, people, post_job  # noqa: F401

JD = """Data Engineer
You will build data pipelines in Python and SQL, and keep data pipelines reliable.
Experience with Airflow and data pipelines. Strong SQL.
Benefits: health insurance, 401(k), paid holidays.
Locations: Seattle, WA, USA; Austin, TX, USA; New York, NY, USA.
"""


def make_version(client, **form):
    response = client.post("/resumes/new", data=form)
    assert response.status_code == 302
    return int(response.headers["Location"].rstrip("/").split("/")[-1])


def form_from(content, **overrides):
    """The editor form as a browser would send it."""
    data = {k: content[k] for k in rc.TEXT_FIELDS}
    for section in rc.SECTIONS:
        for i, entry in enumerate(content[section]):
            for field, value in entry.items():
                data[f"{section}-{i}-{field}"] = value
    data.update(overrides)
    return data


# ---------- Content and keywords ----------

def test_keywords_skip_benefits_and_office_lists():
    keywords = [k.lower() for k in rc.job_keywords(JD, "Python, SQL, Airflow")]
    assert keywords[:3] == ["python", "sql", "airflow"]
    assert "data pipelines" in keywords
    assert not any(word in " ".join(keywords) for word in ("insurance", "seattle", "holidays"))


def test_score_counts_plurals_and_lists_missing():
    content = rc.empty_content()
    content["skills"] = "Python, SQL"
    content["experience"] = [{"title": "Engineer", "org": "Acme", "location": "", "dates": "",
                              "bullets": "Built a data pipeline for billing"}]
    result = rc.score(content, JD, "Python, SQL, Airflow")
    assert "Python" in result["found"] and "data pipelines" in result["found"]
    assert "Airflow" in result["missing"]
    assert 0 < result["score"] < 100


def test_no_job_text_means_no_score():
    assert rc.score(rc.empty_content(), "", "")["score"] is None


def test_bullets_drop_typed_bullet_marks():
    assert rc.bullet_lines("- one\n• two\n\n  * three ") == ["one", "two", "three"]


def test_stored_content_with_missing_or_bad_parts_still_loads():
    content = rc.load('{"name": "A", "experience": [{"title": "T"}, "junk"], "skills": 5}')
    assert content["name"] == "A" and content["skills"] == ""
    assert content["experience"] == [{"title": "T", "org": "", "location": "", "dates": "", "bullets": ""}]
    assert rc.load("not json")["projects"] == []


def test_pdf_is_real_text_an_ats_can_read():
    content = rc.empty_content()
    content.update(name="Deepthi Priya Busi", email="d@example.com", skills="Python, SQL, Airflow",
                   summary="Data engineer — 2 years at Accenture.")
    content["experience"] = [{"title": "Associate", "org": "Accenture", "location": "Hyderabad",
                              "dates": "Jun 2023 – Aug 2025", "bullets": "Built 50 data pipelines"}]
    data = rc.to_pdf(content)
    assert data.startswith(b"%PDF")
    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(data)).pages)
    for words in ("Deepthi Priya Busi", "EXPERIENCE", "Accenture", "Built 50 data pipelines", "Airflow"):
        assert words in text


# ---------- Pages ----------

def test_new_resume_is_filled_from_the_profile(client, logged_in, app):
    client.post("/skills/add", data={"skill_name": "Python, SQL"})
    client.post("/experience/add", data={"company": "Accenture", "job_title": "Associate",
                                         "start_date": "2023-06", "end_date": "2025-08",
                                         "description": "Kept 50 pipelines healthy"})
    vid = make_version(client)
    with app.app_context():
        content = rc.load(db.session.get(ResumeVersion, vid).content_json)
    assert content["name"] == "Test User" and content["email"] == "test@example.com"
    assert "Python" in content["skills"]
    assert content["experience"][0]["org"] == "Accenture"
    assert content["experience"][0]["dates"] == "Jun 2023 – Aug 2025"


def test_edit_add_and_remove_entries(client, logged_in, app):
    vid = make_version(client)
    content = rc.empty_content()
    content.update(name="Test User", skills="Python")
    data = form_from(content, version_name="Data roles")
    data.update({"projects-0-name": "Roleflow", "projects-0-tech": "Flask",
                 "projects-0-bullets": "Board and charts"})
    client.post(f"/resumes/{vid}", data=data)
    with app.app_context():
        version = db.session.get(ResumeVersion, vid)
        assert version.name == "Data roles"
        assert rc.load(version.content_json)["projects"][0]["name"] == "Roleflow"

    data["projects-0-remove"] = "1"
    client.post(f"/resumes/{vid}", data=data)
    with app.app_context():
        assert rc.load(db.session.get(ResumeVersion, vid).content_json)["projects"] == []


def test_editor_scores_against_pasted_job_description(client, logged_in):
    vid = make_version(client)
    content = rc.empty_content()
    content.update(name="Test User", skills="Python, SQL")
    client.post(f"/resumes/{vid}", data=form_from(content, target_text=JD, after_save="match"))
    page = client.get(f"/resumes/{vid}").get_data(as_text=True)
    assert "Keyword match" in page and "Airflow" in page
    assert 'class="chip-missing"' in page and 'class="chip-found"' in page


def test_pdf_download(client, logged_in):
    vid = make_version(client)
    response = client.get(f"/resumes/{vid}/pdf")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert "attachment" in response.headers["Content-Disposition"]


def test_copy_and_delete(client, logged_in, app):
    vid = make_version(client, name="Base")
    client.post(f"/resumes/{vid}/copy")
    with app.app_context():
        assert ResumeVersion.query.filter_by(name="Copy of Base").count() == 1
    client.post(f"/resumes/{vid}/delete")
    with app.app_context():
        assert db.session.get(ResumeVersion, vid) is None


def test_other_people_cannot_see_or_change_a_resume(client, auth, app):
    auth.register(email="a@example.com")
    auth.login(email="a@example.com")
    vid = make_version(client, name="Secret resume")
    auth.logout()
    auth.register(email="b@example.com")
    auth.login(email="b@example.com")
    assert client.get(f"/resumes/{vid}").status_code == 404
    assert client.get(f"/resumes/{vid}/pdf").status_code == 404
    assert client.post(f"/resumes/{vid}", data={"name": "x"}).status_code == 404
    assert client.post(f"/resumes/{vid}/delete").status_code == 404
    assert client.post("/resumes/new", data={"from": vid}).status_code == 404
    assert b"Secret resume" not in client.get("/resumes").data


def test_resume_pages_need_login(client):
    assert "/login" in client.get("/resumes").headers["Location"]


# ---------- Tailoring and Easy Apply ----------

def test_tailor_for_a_job_and_send_it_with_easy_apply(app, people):
    login(people, EMPLOYER)
    post_job(people)
    jid = job_id(app)
    login(people, SEEKER)

    page = people.get(f"/jobs/{jid}").get_data(as_text=True)
    assert "Tailor a resume for this job" in page

    vid = make_version(people, job_id=jid)
    assert "Data Engineer I" in people.get(f"/resumes/{vid}").get_data(as_text=True)
    assert "Open resume" in people.get(f"/jobs/{jid}").get_data(as_text=True)

    apply_page = people.get(f"/jobs/{jid}/apply").get_data(as_text=True)
    assert f'value="built-{vid}"' in apply_page

    response = people.post(f"/jobs/{jid}/apply", data={"resume_source": f"built-{vid}", "note": "Hi"},
                           content_type="multipart/form-data")
    assert response.status_code == 302
    with app.app_context():
        submission = Submission.query.one()
        assert submission.resume_data.startswith(b"%PDF")
        assert submission.resume_filename == "Deepthi_Priya_Busi_Resume.pdf"


def test_cannot_send_someone_elses_built_resume(app, people):
    login(people, EMPLOYER)
    post_job(people)
    jid = job_id(app)
    login(people, OTHER)
    other_vid = make_version(people)
    login(people, SEEKER)
    response = people.post(f"/jobs/{jid}/apply", data={"resume_source": f"built-{other_vid}"},
                           content_type="multipart/form-data")
    assert response.status_code == 404
    with app.app_context():
        assert Submission.query.count() == 0


def test_deleting_an_employer_keeps_resumes_tailored_for_their_jobs(app, people):
    login(people, EMPLOYER)
    post_job(people)
    jid = job_id(app)
    login(people, SEEKER)
    vid = make_version(people, job_id=jid)
    login(people, EMPLOYER)
    people.post("/account/delete", data={"password": "password123"})
    with app.app_context():
        version = db.session.get(ResumeVersion, vid)
        assert version is not None and version.job_id is None


def test_account_export_and_delete_include_built_resumes(client, logged_in, app):
    make_version(client, name="Exported")
    exported = json.loads(client.get("/account/export").data)
    assert exported["built_resumes"][0]["name"] == "Exported"
    client.post("/account/delete", data={"password": "password123"})
    with app.app_context():
        assert ResumeVersion.query.count() == 0


def test_employers_are_sent_to_their_posts(app, people):
    login(people, EMPLOYER)
    response = people.get("/resumes")
    assert response.status_code == 302 and "/employer" in response.headers["Location"]


def test_pdf_handles_long_text_and_many_pages():
    content = rc.empty_content()
    content["name"] = "A" * 100
    content["experience"] = [{"title": "T" * 120, "org": "Very long company name " * 6,
                              "location": "Somewhere", "dates": "Jan 2020 – Present",
                              "bullets": "\n".join(f"Bullet number {i} " + "word " * 40 for i in range(40))}
                             for _ in range(3)]
    data = rc.to_pdf(content)
    assert len(PdfReader(io.BytesIO(data)).pages) > 1
