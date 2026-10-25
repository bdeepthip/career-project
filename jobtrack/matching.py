"""
Match Score: compares a user's profile skills with a job's skills.
"""

import re

# Skills the Match Checker looks for in a pasted job description.
# Single-letter or common-word skills (like "R" or "Go") are left out
# because they create false matches in normal English text.
KNOWN_SKILLS = [
    "Python", "SQL", "Java", "JavaScript", "TypeScript", "C++", "C#",
    "Scala", "HTML", "CSS", "React", "Node.js", "Flask", "Django",
    "FastAPI", "REST API", "Git", "Docker", "Kubernetes", "AWS", "Azure",
    "GCP", "Linux", "Pandas", "NumPy", "Scikit-learn", "Machine Learning",
    "Spark", "PySpark", "Airflow", "Kafka", "Snowflake", "Databricks",
    "ETL", "Data Modeling", "Data Warehousing", "Tableau", "Power BI",
    "Excel", "MongoDB", "PostgreSQL", "MySQL", "Jenkins", "CI/CD",
]

# Compiled once when the app starts instead of on every request
_SKILL_PATTERNS = [
    (skill, re.compile(r"(?<![a-z0-9+#])" + re.escape(skill.lower()) + r"(?![a-z0-9+#])"))
    for skill in KNOWN_SKILLS
]


def parse_skills(skills_text):
    """'Python, Flask, SQL' -> {'python': 'Python', ...}.
    Lowercase keys make matching case-insensitive; values keep the
    original spelling for display."""

    skills = {}
    for skill in (skills_text or "").split(","):
        skill = skill.strip()
        if skill:
            skills[skill.lower()] = skill
    return skills


def get_user_skills(db, user_id):
    return {
        row["skill_name"].strip().lower()
        for row in db.execute(
            "SELECT skill_name FROM skills WHERE user_id = ?", (user_id,)
        )
    }


def calculate_match(user_skills, required_skills_text):
    """Returns (score 0-100, matched_skills, missing_skills).
    user_skills is a set of lowercase skill names."""

    required = parse_skills(required_skills_text)
    if not required:
        return 0, [], []

    matched = [orig for low, orig in required.items() if low in user_skills]
    missing = [orig for low, orig in required.items() if low not in user_skills]
    score = round(len(matched) / len(required) * 100)

    return score, matched, missing


def extract_skills(text):
    """Find which KNOWN_SKILLS appear in text, as 'A, B, C'.
    Whole words only, so 'Java' doesn't match 'JavaScript'."""

    text_lower = (text or "").lower()
    found = [skill for skill, pattern in _SKILL_PATTERNS if pattern.search(text_lower)]
    return ", ".join(found)


def build_learning_plan(db, missing):
    """A course for each missing skill. Returns (plan, total_hours)."""

    resources = {}
    if missing:
        placeholders = ",".join("?" * len(missing))
        for row in db.execute(
            f"SELECT * FROM learning_resources WHERE LOWER(skill_name) IN ({placeholders})",
            [skill.lower() for skill in missing],
        ):
            resources[row["skill_name"].lower()] = row

    plan = [{"skill": s, "resource": resources.get(s.lower())} for s in missing]
    total_hours = sum(
        item["resource"]["estimated_hours"] or 0 for item in plan if item["resource"]
    )
    return plan, total_hours
