-- JobTrack database schema.
-- Every table uses CREATE TABLE IF NOT EXISTS, so running
-- `flask --app app init-db` on an existing database is safe:
-- it only adds tables that are missing and never deletes data.

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);

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
);

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
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    skill_name TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS education (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    institution TEXT NOT NULL,
    degree TEXT NOT NULL,
    field_of_study TEXT,
    start_year TEXT,
    end_year TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

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
);

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
);

CREATE TABLE IF NOT EXISTS learning_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL UNIQUE,
    resource_name TEXT NOT NULL,
    provider TEXT,
    url TEXT,
    estimated_hours INTEGER,
    cost TEXT
);

CREATE TABLE IF NOT EXISTS job_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message_id TEXT,
    sender TEXT,
    subject TEXT,
    body TEXT,
    received_at TEXT,
    detected_status TEXT,
    application_id INTEGER,
    update_note TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (application_id) REFERENCES job_applications(id),
    UNIQUE (user_id, message_id)
);

-- Indexes make "everything for this user" lookups fast as data grows.
CREATE INDEX IF NOT EXISTS idx_applications_user ON job_applications(user_id);
CREATE INDEX IF NOT EXISTS idx_skills_user ON skills(user_id);
CREATE INDEX IF NOT EXISTS idx_emails_user ON job_emails(user_id);
