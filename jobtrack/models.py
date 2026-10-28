"""
Database tables as Python classes (SQLAlchemy models).

Each class is one table, each attribute one column. SQLAlchemy turns
code like `User.query.filter_by(email=email)` into the right SQL for
whichever database is in use: SQLite on your laptop, PostgreSQL in
production. No hand-written SQL needed.

Table and column names match the original schema.sql exactly, so an
existing database.db keeps working without moving any data.
"""

import secrets

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

db = SQLAlchemy()

# Lowercase letters and digits only: email addresses are effectively
# case-insensitive, and this avoids look-alike characters (0/o, 1/l)
TOKEN_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def new_inbound_token():
    """14 random characters (~69 bits): impossible to guess, short enough to read."""
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(14))


class RowAccessMixin:
    """Lets templates keep writing row["company"] as well as row.company,
    so none of the HTML had to change when we moved from sqlite3 rows."""

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class User(RowAccessMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        Index("uq_users_inbound_token", "inbound_token", unique=True),
        Index("uq_users_phone", "phone", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password: Mapped[str] = mapped_column(Text, nullable=False)  # a hash, never plain text
    # The secret part of this user's forwarding address: jt-<token>@INBOUND_DOMAIN
    inbound_token: Mapped[str | None] = mapped_column(
        Text, default=new_inbound_token)
    # Verified mobile number for logging in by text code, "+12155550123".
    # Only set after the person typed the code we texted, so nobody can
    # claim someone else's number.
    phone: Mapped[str | None] = mapped_column(Text)
    # "seeker" (looking for a job) or "employer" (hiring: posts jobs, reviews applicants)
    account_type: Mapped[str] = mapped_column(Text, nullable=False, default="seeker",
                                              server_default="seeker")
    company: Mapped[str | None] = mapped_column(Text)   # employers: the company they hire for

    @property
    def is_employer(self):
        return self.account_type == "employer"

    # cascade="all, delete-orphan": deleting a user deletes everything they own
    applications = relationship("JobApplication", back_populates="user",
                                cascade="all, delete-orphan")
    profile = relationship("Profile", back_populates="user", uselist=False,
                           cascade="all, delete-orphan")
    skills = relationship("Skill", cascade="all, delete-orphan")
    education = relationship("Education", cascade="all, delete-orphan")
    experience = relationship("Experience", cascade="all, delete-orphan")
    emails = relationship("JobEmail", cascade="all, delete-orphan")


class JobApplication(RowAccessMixin, db.Model):
    __tablename__ = "job_applications"
    __table_args__ = (Index("idx_applications_user", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    job_title: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text)
    job_url: Mapped[str | None] = mapped_column(Text)
    date_applied: Mapped[str] = mapped_column(Text, nullable=False)  # "YYYY-MM-DD"
    status: Mapped[str] = mapped_column(Text, nullable=False, default="Applied",
                                        server_default="Applied")
    notes: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="applications")


class Profile(RowAccessMixin, db.Model):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    headline: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(Text)
    target_role: Mapped[str | None] = mapped_column(Text)
    experience_level: Mapped[str | None] = mapped_column(Text)
    preferred_location: Mapped[str | None] = mapped_column(Text)
    about: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="profile")


class Skill(RowAccessMixin, db.Model):
    __tablename__ = "skills"
    __table_args__ = (Index("idx_skills_user", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    skill_name: Mapped[str] = mapped_column(Text, nullable=False)


class Education(RowAccessMixin, db.Model):
    __tablename__ = "education"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    institution: Mapped[str] = mapped_column(Text, nullable=False)
    degree: Mapped[str] = mapped_column(Text, nullable=False)
    field_of_study: Mapped[str | None] = mapped_column(Text)
    start_year: Mapped[str | None] = mapped_column(Text)
    end_year: Mapped[str | None] = mapped_column(Text)


class Experience(RowAccessMixin, db.Model):
    __tablename__ = "experience"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    job_title: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[str | None] = mapped_column(Text)   # "YYYY-MM"
    end_date: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)


class Job(RowAccessMixin, db.Model):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    experience_level: Mapped[str | None] = mapped_column(Text)
    required_skills: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    job_url: Mapped[str | None] = mapped_column(Text)
    posted_date: Mapped[str | None] = mapped_column(Text)
    # Set for jobs posted on GAJ by an employer account (these take Easy Apply).
    # Empty for listings that live on a company's own site.
    posted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    is_open: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    @property
    def easy_apply(self):
        return self.posted_by_user_id is not None


class LearningResource(RowAccessMixin, db.Model):
    __tablename__ = "learning_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    resource_name: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    estimated_hours: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[str | None] = mapped_column(Text)


class JobEmail(RowAccessMixin, db.Model):
    __tablename__ = "job_emails"
    __table_args__ = (
        UniqueConstraint("user_id", "message_id"),
        Index("idx_emails_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    message_id: Mapped[str | None] = mapped_column(Text)
    sender: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[str | None] = mapped_column(Text)  # "YYYY-MM-DD HH:MM"
    detected_status: Mapped[str | None] = mapped_column(Text)
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_applications.id", ondelete="SET NULL"))
    update_note: Mapped[str | None] = mapped_column(Text)

    application = relationship("JobApplication")

    # Used by the Inbox template as item["app_company"] / item["app_title"]
    @property
    def app_company(self):
        return self.application.company if self.application else None

    @property
    def app_title(self):
        return self.application.job_title if self.application else None


class UserActivity(RowAccessMixin, db.Model):
    """Time spent actively using GAJ, per user per day (the screen-time meter)."""
    __tablename__ = "user_activity"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_activity_user_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    day: Mapped[str] = mapped_column(Text, nullable=False)        # "YYYY-MM-DD", the user's local date
    seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_ping: Mapped[str | None] = mapped_column(Text)          # UTC "YYYY-MM-DD HH:MM:SS"


class PhoneCode(RowAccessMixin, db.Model):
    """A one-time text-message code, used only when Twilio isn't set up
    (on your laptop the code is printed in the terminal instead of texted).
    Stores a hash of the code, never the code itself."""
    __tablename__ = "phone_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)   # UTC "YYYY-MM-DD HH:MM:SS"
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Message(RowAccessMixin, db.Model):
    """A direct message between two GAJ users."""
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_messages_pair", "sender_id", "recipient_id"),
        Index("idx_messages_unread", "recipient_id", "read_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)   # "YYYY-MM-DD HH:MM:SS"
    read_at: Mapped[str | None] = mapped_column(Text)


class Block(RowAccessMixin, db.Model):
    """blocker_id doesn't want messages from blocked_id."""
    __tablename__ = "blocks"
    __table_args__ = (UniqueConstraint("blocker_id", "blocked_id", name="uq_block_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blocker_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    blocked_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class Report(RowAccessMixin, db.Model):
    """A user reported another user's messages, for the GAJ team to review."""
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reported_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class Notification(RowAccessMixin, db.Model):
    """Something the user should know about: a message, a status change..."""
    __tablename__ = "notifications"
    __table_args__ = (Index("idx_notifications_user", "user_id", "read_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)       # message, status, inbox, goal, ...
    text: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(Text)                # a GAJ path, e.g. /messages/4
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[str | None] = mapped_column(Text)


class Resume(RowAccessMixin, db.Model):
    """A job seeker's saved resume (PDF), reused for every Easy Apply."""
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[str] = mapped_column(Text, nullable=False)


class Submission(RowAccessMixin, db.Model):
    """An Easy Apply application: what the seeker sent to the employer.
    Keeps its own copy of the resume and profile as they were when sent,
    so later edits don't change an application already submitted."""
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("job_id", "applicant_id", name="uq_submission_job_applicant"),
        Index("idx_submissions_job", "job_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # The applicant's own Dashboard row for this job
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_applications.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(Text)
    profile_json: Mapped[str] = mapped_column(Text, nullable=False)
    resume_filename: Mapped[str | None] = mapped_column(Text)
    resume_data: Mapped[bytes | None] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="New")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)   # UTC
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)   # UTC

    job = relationship("Job")
