"""
Landing page, link previews, icons, getting-started steps, error
pages and the invite link.
"""

from conftest import add_application, make_app, wipe


def test_landing_page_describes_the_features(client):
    page = client.get("/").get_data(as_text=True)
    assert "A board for every application" in page
    assert "Create your free account" in page


def test_link_preview_tags_point_to_a_real_image(client):
    page = client.get("/").get_data(as_text=True)
    assert 'property="og:image"' in page
    assert "http://localhost/static/img/og-image.png" in page
    assert 'name="twitter:card" content="summary_large_image"' in page
    image = client.get("/static/img/og-image.png")
    assert image.status_code == 200 and image.mimetype == "image/png"


def test_favicon_and_robots(client):
    assert client.get("/favicon.ico").status_code == 200
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Disallow: /inbound/" in robots.get_data(as_text=True)


def test_new_account_sees_setup_steps_instead_of_empty_charts(client, logged_in):
    page = client.get("/dashboard").get_data(as_text=True)
    assert "Get set up" in page and "0 of 4 done" in page
    assert 'class="week-chart"' not in page


def test_setup_steps_tick_off_and_charts_appear(client, logged_in):
    add_application(client)
    client.post("/skills/add", data={"skill_name": "Python"})
    page = client.get("/dashboard").get_data(as_text=True)
    assert "of 4 done" in page
    assert 'class="week-chart"' in page
    assert 'setup-step is-done' in page


def test_error_page_shows_the_code_and_a_way_back(client, logged_in):
    response = client.get("/no-such-page")
    page = response.get_data(as_text=True)
    assert response.status_code == 404
    assert 'class="error-code"' in page and ">404<" in page
    assert "Go to your dashboard" in page


def test_invite_link_fills_in_the_code(tmp_path):
    app = make_app(tmp_path, BETA_INVITE_CODE="owls-beta")
    try:
        client = app.test_client()
        page = client.get("/register?invite=owls-beta").get_data(as_text=True)
        assert 'value="owls-beta"' in page
        assert "private beta" in client.get("/").get_data(as_text=True)

        # The wrong code is still refused, and the right one works
        bad = client.post("/register", data={"name": "A", "email": "a@example.com",
                                             "password": "password123", "invite_code": "nope"})
        assert b"private beta" in bad.data
        good = client.post("/register", data={"name": "A", "email": "a@example.com",
                                              "password": "password123", "invite_code": "OWLS-BETA"})
        assert good.status_code == 302
    finally:
        wipe(app)


def test_invite_link_value_is_escaped(tmp_path):
    app = make_app(tmp_path, BETA_INVITE_CODE="owls-beta")
    try:
        page = app.test_client().get('/register?invite="><script>x</script>').get_data(as_text=True)
        assert "<script>x</script>" not in page
    finally:
        wipe(app)
