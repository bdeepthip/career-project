import sqlite3


jobs = [

    (
        "TechNova",
        "Python Backend Developer",
        "Software Development",
        "Philadelphia, PA",
        "Entry Level",
        "Python, Flask, SQL, REST API, Git",
        "Build and maintain backend APIs using Python and Flask. "
        "Work with SQL databases and collaborate with frontend developers.",
        "https://example.com/jobs/python-backend",
        "2026-09-24"
    ),

    (
        "DataVision",
        "Data Analyst",
        "Data Analytics",
        "New York, NY",
        "Entry Level",
        "Python, SQL, Pandas, Excel, Tableau",
        "Analyze business datasets, create dashboards and generate "
        "insights using Python, SQL, Excel and Tableau.",
        "https://example.com/jobs/data-analyst",
        "2026-09-23"
    ),

    (
        "CloudCore",
        "Junior DevOps Engineer",
        "Cloud / DevOps",
        "Remote",
        "Entry Level",
        "Docker, Kubernetes, AWS, Jenkins, Git",
        "Support cloud infrastructure and CI/CD pipelines using "
        "Docker, Kubernetes, AWS and Jenkins.",
        "https://example.com/jobs/devops",
        "2026-09-22"
    ),

    (
        "AI Labs",
        "Machine Learning Engineer",
        "AI / Machine Learning",
        "Boston, MA",
        "1-2 Years",
        "Python, NumPy, Pandas, Scikit-learn, Machine Learning",
        "Develop and evaluate machine learning models and "
        "prepare datasets for AI applications.",
        "https://example.com/jobs/ml-engineer",
        "2026-09-21"
    ),

    (
        "SecureNet",
        "Cybersecurity Analyst",
        "Cybersecurity",
        "Washington, DC",
        "Entry Level",
        "Linux, Networking, Python, Security, SIEM",
        "Monitor security events, investigate suspicious activity "
        "and assist with security operations.",
        "https://example.com/jobs/security-analyst",
        "2026-09-20"
    ),

    (
        "WebWorks",
        "Full Stack Developer",
        "Software Development",
        "Remote",
        "Entry Level",
        "Python, Flask, JavaScript, HTML, CSS, SQL",
        "Develop full-stack web applications using Flask, "
        "JavaScript, HTML, CSS and SQL.",
        "https://example.com/jobs/fullstack",
        "2026-09-19"
    )

]


connection = sqlite3.connect("database.db")
cursor = connection.cursor()


# Prevent duplicate sample data when running this file again
cursor.execute("SELECT COUNT(*) FROM jobs")

job_count = cursor.fetchone()[0]


if job_count == 0:

    cursor.executemany(
        """
        INSERT INTO jobs
        (
            company,
            title,
            domain,
            location,
            experience_level,
            required_skills,
            description,
            job_url,
            posted_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        jobs
    )

    connection.commit()

    print(f"{len(jobs)} sample jobs added successfully!")

else:

    print(
        f"Jobs table already contains {job_count} jobs. "
        "No duplicate sample jobs were added."
    )


connection.close()