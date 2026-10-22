import sqlite3


# (skill, course name, provider, url, estimated hours, cost)
# Hours are rough estimates. Check each link before relying on it.
resources = [
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


connection = sqlite3.connect("database.db")
cursor = connection.cursor()

# INSERT OR IGNORE skips skills that already exist,
# so running this file twice won't create duplicates.
cursor.executemany(
    """
    INSERT OR IGNORE INTO learning_resources
    (skill_name, resource_name, provider, url, estimated_hours, cost)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    resources
)

connection.commit()
print(f"{cursor.rowcount} learning resources added.")
connection.close()