from conftest import add_application


def test_add_and_list(client, logged_in):
    response = add_application(client)
    assert response.status_code == 200
    assert b"Added Microsoft." in response.data
    assert b"Microsoft" in client.get("/dashboard").data


def test_dashboard_counts(client, logged_in):
    add_application(client, company="A", status="Applied")
    add_application(client, company="B", status="Interview")
    add_application(client, company="C", status="Interview")
    page = client.get("/dashboard").get_data(as_text=True)
    assert '<span class="status-count">3</span>' in page   # total
    assert '<span class="status-count">2</span>' in page   # interviews


def test_filter_by_status(client, logged_in):
    add_application(client, company="Alpha", status="Applied")
    add_application(client, company="Beta", status="Offer")
    page = client.get("/dashboard?status=Offer").data
    assert b"Beta" in page and b"Alpha" not in page


def test_search(client, logged_in):
    add_application(client, company="Alpha")
    add_application(client, company="Beta")
    page = client.get("/dashboard?search=alp").data
    assert b"Alpha" in page and b"Beta" not in page


def test_required_fields(client, logged_in):
    response = add_application(client, company="")
    assert response.status_code == 400
    assert b"Company is required" in response.data


def test_invalid_status_rejected(client, logged_in):
    response = add_application(client, status="Hired!!")
    assert response.status_code == 400


def test_invalid_date_rejected(client, logged_in):
    response = add_application(client, date_applied="yesterday")
    assert response.status_code == 400


def test_javascript_url_rejected(client, logged_in):
    response = add_application(client, job_url="javascript:alert(document.cookie)")
    assert response.status_code == 400
    assert b"must start with http" in response.data


def test_edit(client, logged_in):
    add_application(client)
    response = client.post("/applications/edit/1", data={
        "company": "Microsoft", "job_title": "Software Engineer II", "location": "",
        "job_url": "", "date_applied": "2026-10-20", "status": "Interview", "notes": "Round 1",
    })
    assert response.status_code == 302
    page = client.get("/dashboard").data
    assert b"Software Engineer II" in page and b"Round 1" in page


def test_delete(client, logged_in):
    add_application(client)
    response = client.post("/applications/delete/1", follow_redirects=True)
    assert b"Deleted Microsoft." in response.data
    assert b"Microsoft" not in client.get("/dashboard").data


def test_users_cannot_see_or_change_each_others_applications(client, auth):
    # User A adds an application
    auth.register(email="a@example.com")
    auth.login(email="a@example.com")
    add_application(client, company="SecretCo")
    auth.logout()

    # User B tries to view, edit, and delete it
    auth.register(email="b@example.com")
    auth.login(email="b@example.com")
    assert b"SecretCo" not in client.get("/dashboard").data
    assert client.get("/applications/edit/1").status_code == 404
    assert client.post("/applications/edit/1", data={
        "company": "Hacked", "job_title": "x", "date_applied": "2026-10-20", "status": "Applied",
    }).status_code == 404
    assert client.post("/applications/delete/1").status_code == 404
    auth.logout()

    # User A's application is untouched
    auth.login(email="a@example.com")
    assert b"SecretCo" in client.get("/dashboard").data


def test_add_form_prefills_today(client, logged_in):
    from datetime import date
    assert date.today().isoformat().encode() in client.get("/applications/add").data
