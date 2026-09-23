import sqlite3


def init_db():

    connection = sqlite3.connect("database.db")

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        company TEXT NOT NULL,
        job_title TEXT NOT NULL,
        location TEXT,
        job_url TEXT,
        date_applied TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Applied',
        notes TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
""")

    connection.commit()

    connection.close()


if __name__ == "__main__":
    init_db()
    print("Database created successfully!")