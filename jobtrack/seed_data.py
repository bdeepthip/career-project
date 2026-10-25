"""
Sample data for the Jobs page and the learning-plan popup.

The jobs are SAMPLE listings (example.com links). The Jobs page labels
them as samples until real job listings are added (roadmap phase 6).
"""

SAMPLE_JOBS = [
    ("TechNova", "Python Backend Developer", "Software Development",
     "Philadelphia, PA", "Entry Level", "Python, Flask, SQL, REST API, Git",
     "Build and maintain backend APIs using Python and Flask. "
     "Work with SQL databases and collaborate with frontend developers.",
     "https://example.com/jobs/python-backend", "2026-09-24"),
    ("DataVision", "Data Analyst", "Data Analytics", "New York, NY",
     "Entry Level", "Python, SQL, Pandas, Excel, Tableau",
     "Analyze business datasets, create dashboards and generate "
     "insights using Python, SQL, Excel and Tableau.",
     "https://example.com/jobs/data-analyst", "2026-09-23"),
    ("CloudCore", "Junior DevOps Engineer", "Cloud / DevOps", "Remote",
     "Entry Level", "Docker, Kubernetes, AWS, Jenkins, Git",
     "Support cloud infrastructure and CI/CD pipelines using "
     "Docker, Kubernetes, AWS and Jenkins.",
     "https://example.com/jobs/devops", "2026-09-22"),
    ("AI Labs", "Machine Learning Engineer", "AI / Machine Learning",
     "Boston, MA", "1-2 Years",
     "Python, NumPy, Pandas, Scikit-learn, Machine Learning",
     "Develop and evaluate machine learning models and "
     "prepare datasets for AI applications.",
     "https://example.com/jobs/ml-engineer", "2026-09-21"),
    ("SecureNet", "Cybersecurity Analyst", "Cybersecurity",
     "Washington, DC", "Entry Level",
     "Linux, Networking, Python, Security, SIEM",
     "Monitor security events, investigate suspicious activity "
     "and assist with security operations.",
     "https://example.com/jobs/security-analyst", "2026-09-20"),
    ("WebWorks", "Full Stack Developer", "Software Development", "Remote",
     "Entry Level", "Python, Flask, JavaScript, HTML, CSS, SQL",
     "Develop full-stack web applications using Flask, "
     "JavaScript, HTML, CSS and SQL.",
     "https://example.com/jobs/fullstack", "2026-09-19"),
]

# (skill, course, provider, url, estimated hours, cost)
# Hours are rough estimates; all courses are free.
LEARNING_RESOURCES = [
    ("Python", "Python", "Kaggle Learn",
     "https://www.kaggle.com/learn/python", 5, "Free"),
    ("SQL", "Intro to SQL", "Kaggle Learn",
     "https://www.kaggle.com/learn/intro-to-sql", 3, "Free"),
    ("Pandas", "Pandas", "Kaggle Learn",
     "https://www.kaggle.com/learn/pandas", 4, "Free"),
    ("Machine Learning", "Intro to Machine Learning", "Kaggle Learn",
     "https://www.kaggle.com/learn/intro-to-machine-learning", 3, "Free"),
    ("Flask", "Flask Tutorial", "Flask Docs",
     "https://flask.palletsprojects.com/en/stable/tutorial/", 6, "Free"),
    ("Git", "Pro Git Book", "git-scm.com",
     "https://git-scm.com/book/en/v2", 10, "Free"),
    ("Docker", "Get Started", "Docker Docs",
     "https://docs.docker.com/get-started/", 6, "Free"),
    ("JavaScript", "JavaScript Certification", "freeCodeCamp",
     "https://www.freecodecamp.org/learn", 40, "Free"),
    ("HTML", "Responsive Web Design", "freeCodeCamp",
     "https://www.freecodecamp.org/learn", 30, "Free"),
    ("CSS", "Responsive Web Design", "freeCodeCamp",
     "https://www.freecodecamp.org/learn", 30, "Free"),
    ("AWS", "Cloud Practitioner Essentials", "AWS Skill Builder",
     "https://skillbuilder.aws/", 6, "Free"),
    ("Kubernetes", "Kubernetes Basics", "kubernetes.io",
     "https://kubernetes.io/docs/tutorials/kubernetes-basics/", 4, "Free"),
]


def seed(db):
    """Insert sample data. Skips anything already there.
    Returns (jobs_added, resources_added)."""

    jobs_added = 0
    if db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0:
        db.executemany(
            """
            INSERT INTO jobs
            (company, title, domain, location, experience_level,
             required_skills, description, job_url, posted_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            SAMPLE_JOBS,
        )
        jobs_added = len(SAMPLE_JOBS)

    before = db.execute("SELECT COUNT(*) FROM learning_resources").fetchone()[0]
    db.executemany(
        """
        INSERT OR IGNORE INTO learning_resources
        (skill_name, resource_name, provider, url, estimated_hours, cost)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        LEARNING_RESOURCES,
    )
    after = db.execute("SELECT COUNT(*) FROM learning_resources").fetchone()[0]

    db.commit()
    return jobs_added, after - before
