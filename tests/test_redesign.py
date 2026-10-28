"""
New look: sidebar, daily line, screen time, date-posted filter, profile strength.
"""

from datetime import date, datetime, timedelta, timezone

from jobtrack.activity import format_duration
from jobtrack.daily import DAILY_LINES, line_for
from jobtrack.models import Job, UserActivity, db
from jobtrack.timefmt import time_ago


# ---------- Sidebar ----------

def test_sidebar_has_every_section_and_marks_the_current_one(client, logged_in):
    page = client.get("/jobs").get_data(as_text=True)
    for label in ("Dashboard", "Jobs", "Profile", "Inbox", "Match Checker", "Account", "Sign out"):
        assert f"<span>{label}</span>" in page
    assert 'href="/jobs" class="nav-item is-active"' in page
    assert page.count('aria-current="page"') == 1


def test_public_pages_have_no_sidebar(client):
    assert b'class="sidebar"' not in client.get("/login").data


# ---------- Line of the day ----------

def test_daily_line_changes_each_day_and_repeats_after_the_list():
    today = date(2026, 10, 28)
    assert line_for(today) != line_for(today + timedelta(days=1))
    assert line_for(today) == line_for(today + timedelta(days=len(DAILY_LINES)))


def test_daily_line_on_login_and_dashboard(client, logged_in):
    assert line_for().encode() in client.get("/dashboard").data
    logged_in.logout()
    assert line_for().encode() in client.get("/login").data


# ---------- Screen time ----------

def ping(client, offset=300):
    return client.post("/activity/ping", json={"tz_offset_minutes": offset})


def test_ping_counts_30_seconds(client, logged_in):
    data = ping(client).get_json()
    assert data["seconds"] == 30 and data["display"] == "0m"


def test_two_tabs_are_not_double_counted(app, client, logged_in):
    ping(client)
    assert ping(client).get_json()["seconds"] == 30  # second ping within 25 s: ignored


def test_time_adds_up_after_the_gap(app, client, logged_in):
    ping(client)
    with app.app_context():
        row = UserActivity.query.one()
        row.last_ping = (datetime.now(timezone.utc) - timedelta(seconds=31)).strftime("%Y-%m-%d %H:%M:%S")
        db.session.commit()
    assert ping(client).get_json()["seconds"] == 60


def test_screen_time_uses_the_users_own_date(app, client, logged_in):
    ping(client, offset=-14 * 60)  # UTC+14: already "tomorrow" for most of the world
    with app.app_context():
        day = UserActivity.query.one().day
    expected = (datetime.now(timezone.utc) + timedelta(hours=14)).date().isoformat()
    assert day == expected


def test_screen_time_shows_in_sidebar_and_on_jobs(app, client, logged_in):
    with app.app_context():
        from jobtrack.models import User
        user = User.query.one()
        utc_today = datetime.now(timezone.utc).date().isoformat()  # no offset sent yet = UTC
        db.session.add(UserActivity(user_id=user.id, day=utc_today,
                                    seconds=2 * 3600 + 5 * 60))
        db.session.commit()
    page = client.get("/jobs").get_data(as_text=True)
    assert page.count("2h 05m") == 2  # sidebar meter + jobs banner
    assert 'value="30"' in page       # 2h05m of 7h is 30%
    assert "at least 7 hours a day" in page


def test_ping_needs_login(client):
    assert ping(client).status_code == 302


def test_screen_time_is_exported_and_deleted_with_the_account(app, client, logged_in):
    ping(client)
    assert client.get("/account/export").get_json()["screen_time"][0]["seconds"] == 30
    client.post("/account/delete", data={"password": "password123"})
    with app.app_context():
        assert UserActivity.query.count() == 0


def test_format_duration():
    assert format_duration(59) == "0m"
    assert format_duration(25 * 60) == "25m"
    assert format_duration(7 * 3600 + 3 * 60) == "7h 03m"


# ---------- Date posted ----------

def add_job(app, title, posted):
    with app.app_context():
        db.session.add(Job(company="Acme", title=title, domain="Data Science",
                           location="Remote", required_skills="Python", posted_date=posted))
        db.session.commit()


def test_past_24_hours_filter(app, client, logged_in):
    now = datetime.now()
    add_job(app, "Fresh Role", (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M"))
    add_job(app, "Older Role", (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M"))

    page = client.get("/jobs?posted=1").get_data(as_text=True)
    assert "Fresh Role" in page and "Older Role" not in page
    assert "Posted 3 hours ago" in page

    page = client.get("/jobs?posted=3").get_data(as_text=True)
    assert "Fresh Role" in page and "Older Role" in page


def test_unknown_posted_value_is_ignored(client, logged_in):
    assert client.get("/jobs?posted=999").status_code == 200


def test_month_label():
    from jobtrack.timefmt import month_label
    assert month_label("2022-08") == "Aug 2022"
    assert month_label("") == "" and month_label("someday") == "someday"


def test_time_ago():
    now = datetime(2026, 10, 28, 15, 0)
    assert time_ago("2026-10-28 14:58", now) == "2 min ago"
    assert time_ago("2026-10-28 10:00", now) == "5 hours ago"
    assert time_ago("2026-10-28", now) == "today"
    assert time_ago("2026-10-27", now) == "yesterday"
    assert time_ago("2026-10-24", now) == "4 days ago"
    assert time_ago("2026-10-07", now) == "3 weeks ago"
    assert time_ago("2026-03-02", now) == "Mar 2"
    assert time_ago("2025-03-02", now) == "Mar 2, 2025"
    assert time_ago("not a date", now) == "not a date"


# ---------- Profile ----------

def test_profile_strength_grows_as_you_fill_it_in(client, logged_in):
    page = client.get("/profile").get_data(as_text=True)
    assert "0%" in page and "Add headline" in page

    client.post("/profile", data={"headline": "Data Engineer", "location": "Philadelphia, PA",
                                  "target_role": "Data Engineer", "about": "I build pipelines."})
    client.post("/skills/add", data={"skill_name": "Python, SQL, Git, Airflow, Tableau"})
    page = client.get("/profile").get_data(as_text=True)
    assert "71%" in page            # 5 of 7 done
    assert "Add education" in page and "Add headline" not in page
    assert ">TU</div>" in page      # initials of "Test User"
