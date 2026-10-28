def test_add_multiple_skills_and_no_duplicates(client, logged_in):
    client.post("/skills/add", data={"skill_name": "Python, SQL, python"})
    page = client.get("/profile").get_data(as_text=True)
    assert page.count(">Python<") == 1 and ">SQL<" in page


def test_profile_save_and_update(client, logged_in):
    data = {"headline": "Headline One", "phone": "", "location": "", "domain": "Data Analytics",
            "target_role": "", "experience_level": "1-2 Years", "preferred_location": "", "about": ""}
    client.post("/profile", data=data)
    data["headline"] = "Headline Two"
    client.post("/profile", data=data)
    page = client.get("/profile").data
    assert b"Headline Two" in page and b"Headline One" not in page


def test_jobs_show_match_score(client, logged_in):
    client.post("/skills/add", data={"skill_name": "Python, SQL, Git"})
    page = client.get("/jobs").data
    assert b"<strong>60%</strong> match" in page   # TechNova: 3 of 5 skills


def test_job_details_learning_plan(client, logged_in):
    client.post("/skills/add", data={"skill_name": "Python, SQL, Git"})
    page = client.get("/jobs/1").data
    assert b"Flask Tutorial" in page      # course for the missing Flask skill
    assert b"Search tutorials" in page    # REST API has no course


def test_match_checker(client, logged_in):
    client.post("/skills/add", data={"skill_name": "Python"})
    page = client.post("/match", data={"job_description": "Requires Python and SQL."}).data
    assert b"50%" in page


def test_match_checker_no_skills_found(client, logged_in):
    page = client.post("/match", data={"job_description": "hello world"}).data
    assert b"No known skills were found" in page


def test_missing_job_is_404(client, logged_in):
    assert client.get("/jobs/999").status_code == 404
