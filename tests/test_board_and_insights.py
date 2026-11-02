"""
The Kanban board, the dashboard charts and the light/dark theme.
"""

from datetime import date, timedelta

from conftest import add_application, make_app, wipe

from jobtrack import insights
from jobtrack.models import JobApplication, db


# ---------- Board ----------

def test_board_shows_each_application_in_its_status_column(client, logged_in):
    add_application(client, company="Alpha", status="Applied")
    add_application(client, company="Beta", status="Interview")
    page = client.get("/board").get_data(as_text=True)

    assert 'data-column="Interview"' in page
    interview = page.split('data-column="Interview"')[1].split('data-column="Offer"')[0]
    applied = page.split('data-column="Applied"')[1].split('data-column="Interview"')[0]
    assert "Beta" in interview and "Alpha" not in interview
    assert "Alpha" in applied


def test_board_requires_login(client):
    response = client.get("/board")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_move_with_json_for_the_drag_and_drop(client, logged_in, app):
    add_application(client, company="Alpha")
    response = client.post("/applications/1/status", data={"status": "Interview"},
                           headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert response.get_json() == {"id": 1, "status": "Interview"}
    with app.app_context():
        assert db.session.get(JobApplication, 1).status == "Interview"


def test_move_with_the_menu_form_redirects_to_the_board(client, logged_in, app):
    add_application(client, company="Alpha")
    response = client.post("/applications/1/status", data={"status": "Offer"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/board")
    with app.app_context():
        assert db.session.get(JobApplication, 1).status == "Offer"


def test_move_rejects_an_unknown_status(client, logged_in, app):
    add_application(client, company="Alpha")
    response = client.post("/applications/1/status", data={"status": "Hired!!"},
                           headers={"Accept": "application/json"})
    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(JobApplication, 1).status == "Applied"


def test_cannot_move_someone_elses_application(client, auth, app):
    auth.register(email="a@example.com")
    auth.login(email="a@example.com")
    add_application(client, company="SecretCo")
    auth.logout()

    auth.register(email="b@example.com")
    auth.login(email="b@example.com")
    assert client.post("/applications/1/status", data={"status": "Offer"}).status_code == 404
    assert b"SecretCo" not in client.get("/board").data
    with app.app_context():
        assert db.session.get(JobApplication, 1).status == "Applied"


def test_move_needs_a_csrf_token(tmp_path):
    app = make_app(tmp_path, WTF_CSRF_ENABLED=True)
    try:
        client = app.test_client()
        response = client.post("/applications/1/status", data={"status": "Offer"})
        assert response.status_code == 400
    finally:
        wipe(app)


# ---------- Dashboard numbers ----------

def test_weekly_counts_fill_empty_weeks_and_skip_old_and_future_dates(client, logged_in, app):
    today = date(2026, 11, 4)                     # a Wednesday
    this_monday = date(2026, 11, 2)
    for day in [this_monday, today, this_monday - timedelta(days=1),
                this_monday - timedelta(weeks=9), today + timedelta(days=30)]:
        add_application(client, date_applied=day.isoformat())

    with app.app_context():
        weeks = insights.weekly_counts(1, today=today)

    assert len(weeks) == 8
    assert weeks[-1]["start"] == this_monday and weeks[-1]["count"] == 2
    assert weeks[-2]["count"] == 1               # the Sunday before
    assert sum(w["count"] for w in weeks) == 3   # 9 weeks ago and next month left out


def test_chart_bars_scale_to_a_tidy_axis():
    weeks = [{"label": str(i), "count": c, "start": None} for i, c in enumerate([0, 1, 5, 0])]
    chart = insights.chart_bars(weeks, width=100, height=80, gap=0)
    assert chart["top"] == 8
    tallest = chart["bars"][2]
    assert tallest["height"] == 50.0 and tallest["y"] == 30.0
    assert chart["bars"][0]["height"] == 0
    assert chart["bars"][1]["height"] >= 3       # a single application stays visible
    assert chart["bars"][-1]["current"]


def test_rates_and_pipeline():
    counts = {"Applied": 6, "Interview": 2, "Offer": 1, "Rejected": 1}
    assert insights.rates(counts) == {"response": 40, "interview": 30}
    assert [s["percent"] for s in insights.pipeline(counts)] == [60, 20, 10, 10]
    assert insights.rates({"Applied": 0}) == {"response": None, "interview": None}


def test_dashboard_shows_rates_and_chart(client, logged_in):
    add_application(client, company="A", status="Applied", date_applied=date.today().isoformat())
    add_application(client, company="B", status="Interview", date_applied=date.today().isoformat())
    page = client.get("/dashboard").get_data(as_text=True)
    assert "Response rate" in page and "50%" in page
    assert 'class="week-chart"' in page
    assert "This week" in page


# ---------- Theme ----------

def test_dark_theme_by_default_and_light_from_cookie(client):
    assert 'data-theme="dark"' in client.get("/login").get_data(as_text=True)
    client.set_cookie("theme", "light")
    assert 'data-theme="light"' in client.get("/login").get_data(as_text=True)


def test_theme_cookie_cannot_inject_markup(client):
    client.set_cookie("theme", '"><script>alert(1)</script>')
    page = client.get("/login").get_data(as_text=True)
    assert "<script>alert(1)" not in page
    assert 'data-theme="dark"' in page
