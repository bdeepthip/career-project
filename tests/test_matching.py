from jobtrack.matching import calculate_match, extract_skills, parse_skills


def test_parse_skills_is_case_insensitive():
    assert parse_skills(" Python, sql ,,Git") == {"python": "Python", "sql": "sql", "git": "Git"}


def test_calculate_match():
    score, matched, missing = calculate_match({"python", "sql", "git"}, "Python, Flask, SQL, REST API, Git")
    assert score == 60
    assert matched == ["Python", "SQL", "Git"]
    assert missing == ["Flask", "REST API"]


def test_calculate_match_with_no_required_skills():
    assert calculate_match({"python"}, "") == (0, [], [])


def test_extract_skills_whole_words():
    text = "Knowledge of SQL, data modeling and Python. JavaScript a plus. C++ or C#."
    found = extract_skills(text).split(", ")
    assert set(found) == {"Python", "SQL", "JavaScript", "C++", "C#", "Data Modeling"}
    assert "Java" not in found   # not fooled by "JavaScript"


def test_extract_skills_ignores_partial_words():
    assert "Git" not in extract_skills("We use digital tools").split(", ")
