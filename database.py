import sqlite3


def init_db():

    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()

    # ==========================================
    # 1. USERS TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)


    # ==========================================
    # 2. JOB APPLICATIONS TABLE
    # ==========================================

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


    # ==========================================
    # 3. PROFESSIONAL PROFILES TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            headline TEXT,
            phone TEXT,
            location TEXT,
            domain TEXT,
            target_role TEXT,
            experience_level TEXT,
            preferred_location TEXT,
            about TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)


    # ==========================================
    # 4. SKILLS TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            skill_name TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    # ==========================================
    # 5. EDUCATION TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS education (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        institution TEXT NOT NULL,
        degree TEXT NOT NULL,
        field_of_study TEXT,
        start_year TEXT,
        end_year TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)


    # ==========================================
    # 6. EXPERIENCE TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experience (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        company TEXT NOT NULL,
        job_title TEXT NOT NULL,
        location TEXT,
        start_date TEXT,
        end_date TEXT,
        description TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ==========================================
    # 7. JOBS TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        title TEXT NOT NULL,
        domain TEXT,
        location TEXT,
        experience_level TEXT,
        required_skills TEXT,
        description TEXT,
        job_url TEXT,
        posted_date TEXT
        )
    """)

        # ==========================================
    # 8. LEARNING RESOURCES TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        skill_name TEXT NOT NULL UNIQUE,
        resource_name TEXT NOT NULL,
        provider TEXT,
        url TEXT,
        estimated_hours INTEGER,
        cost TEXT
        )
    """)

    # Save database changes
    connection.commit()

    # Close database connection
    connection.close()


if __name__ == "__main__":
    init_db()
    print("Database created successfully!")