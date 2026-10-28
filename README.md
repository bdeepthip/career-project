# GAJ (Get A Job)

A job search app: track every application, see how your skills match a
job, Easy Apply to jobs employers post on GAJ, message other users, and
let job emails update your application statuses.

## Features

- **Dashboard**: every application with status counts, search and filters
- **Match Score**: compares your profile skills with a job's required skills
- **Match Checker**: paste any job description and get a score
- **Learning plan**: free courses and time estimates for missing skills
- **Accounts**: password reset by email, change password (signs out
  other devices), download all your data, delete your account
- **Inbox**: paste a job email; GAJ detects Applied / Interview /
  Offer / Rejected, matches the company, and updates the application
  (never moving a status backwards)
- **Forwarding address**: forward job emails to your private GAJ address
  and statuses update on their own
- **Easy Apply**: apply to jobs posted on GAJ with your profile, resume
  PDF and a note; withdraw any time
- **Employer accounts**: post jobs, review applicants with a match score,
  download resumes, and move people through New → Reviewing → Interview →
  Offer / Rejected (the applicant's Dashboard updates and they're notified)
- **Messages**: direct messages between users, with block and report
- **Notifications**: new messages, status changes, new jobs that match you
- **Phone log-in**: log in with a text-message code (Twilio Verify)
- **Daily line and screen time**: a new line of encouragement every day,
  and a meter of active time on GAJ toward a 7-hour daily goal

## How it works

| Piece | File |
|---|---|
| App setup, security headers, error pages | `jobtrack/__init__.py` |
| Settings (development / production) | `jobtrack/config.py` |
| Tables (SQLAlchemy models) | `jobtrack/models.py` |
| Database commands (`init-db`, `seed`) | `jobtrack/db.py` |
| Versioned schema changes (Alembic) | `migrations/versions/` |
| Accounts, password reset, `@login_required` | `jobtrack/auth.py` |
| Account settings, export, deletion | `jobtrack/account.py` |
| Signed, expiring reset tokens | `jobtrack/tokens.py` |
| Outgoing email | `jobtrack/mailer.py` |
| Applications and dashboard | `jobtrack/applications.py` |
| Profile, skills, education, experience | `jobtrack/profile.py` |
| Jobs, job details, Match Checker | `jobtrack/jobs.py` |
| Match Score logic | `jobtrack/matching.py` |
| Inbox routes | `jobtrack/inbox.py` |
| Forwarding addresses and the incoming-email webhook | `jobtrack/inbound.py` |
| Privacy Policy and Terms pages | `jobtrack/pages.py` |
| Easy Apply, resume PDFs | `jobtrack/apply.py`, `jobtrack/resumes.py` |
| Employer job posts and applicants | `jobtrack/employer.py` |
| Messages, notifications | `jobtrack/messages.py`, `jobtrack/notifications.py` |
| Phone log-in by text code | `jobtrack/phone.py`, `jobtrack/sms.py` |
| Screen time, daily line | `jobtrack/activity.py`, `jobtrack/daily.py` |
| CSRF and rate-limit setup | `jobtrack/extensions.py` |
| Deployment (Render) | `render.yaml`, `LAUNCH.md` |
| Email status detection and matching | `jobtrack/email_parser.py` |
| Form validation | `jobtrack/validation.py` |

Match Score is keyword-based: it looks for over 40 common technical
skills in a job description and compares them with your profile.
Email status detection is rule-based (phrases like "pleased to offer"
or "not moving forward"), so unusual wording can be missed; the Inbox
lets you fix a match by hand.

## Forwarding address

Every user gets a private address like `jt-7fk2m9qa4xwd@in.yourdomain.com`
(shown on the Inbox page). They add a Gmail filter that forwards job
emails there, and applications update without any pasting.

An email service receives mail for `INBOUND_DOMAIN` and posts each
message to `POST /inbound/email` with `INBOUND_WEBHOOK_SECRET`. Supported
formats: raw email (Cloudflare Email Routing with
`deploy/cloudflare-email-worker.js`, free), Postmark JSON, Mailgun and
SendGrid form posts. Details:

- Unknown addresses are ignored; each email lands only in its owner's Inbox
- Retried deliveries are saved once (Message-ID, or a content fingerprint)
- Gmail's forwarding confirmation code is shown in the Inbox
- At most 300 forwarded emails per user per day; a user can replace a
  leaked address in one click, and the old one stops working

## Security

- Passwords stored as salted hashes (Werkzeug)
- CSRF protection on every form (Flask-WTF)
- Every query goes through SQLAlchemy (parameterized) and is scoped to the logged-in user;
  tests confirm one user can't see or change another's data
- Server-side validation of all form input, including blocking
  `javascript:` links
- Session cookies are HttpOnly and SameSite=Lax (Secure in production)
- Safe redirects after login; security headers on every response
- Password reset links are signed, expire after 1 hour, and stop
  working once used; the reset page never reveals who has an account
- Changing a password signs out every other device
- Rate limits on log-in, sign-up and password reset: per network, and
  per account so a password can't be guessed from many addresses
- Content-Security-Policy allows only GAJ's own scripts and styles
  (no inline JavaScript anywhere)
- In production: HTTPS only (HSTS), secure cookies, and the app refuses
  to start with a short SECRET_KEY, a SQLite database, or no email server

## Run it locally

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then set SECRET_KEY
flask --app app init-db
flask --app app seed
python app.py                     # http://127.0.0.1:5001
```

Without email settings in `.env`, password reset emails are printed
in the terminal, so you can copy the link while developing.

## Database

GAJ runs on **SQLite** on your laptop (`database.db`, no setup)
and **PostgreSQL** in production. Set `DATABASE_URL` in `.env` to
switch; nothing else changes.

```bash
flask --app app init-db                      # create or upgrade; never deletes data
flask --app app db migrate -m "add column"   # after changing models.py
flask --app app init-db                      # apply that new migration
```

Every change to the tables is a versioned migration in
`migrations/versions/`, so every copy of the database can be brought
to the same structure safely. A `database.db` created before
migrations existed is upgraded in place, keeping all its data.

## Going live

`LAUNCH.md` walks through putting GAJ online step by step: domain,
hosting (Render), database (Neon), sending and receiving email, the
live-site checklist, and inviting beta testers. It costs about $7 a
month plus the domain.

## Tests

```bash
python -m pytest
# the same tests against PostgreSQL (uses an empty, wipeable database):
TEST_DATABASE_URL=postgresql://user:pass@localhost/jobtrack_test python -m pytest
```

CI runs every test on both SQLite and PostgreSQL. 202 tests cover accounts, password reset, data export and deletion, data privacy between users, CSRF, input
validation, Match Score, email parsing, the Inbox, forwarded email, rate limits and production safety checks.

## Roadmap

1. Foundation: code structure, CSRF, validation, tests (done)
2. Accounts: password reset, account deletion, data export (done)
3. PostgreSQL with migrations (done)
4. A personal email forwarding address for every user (done)
5. Public beta: deployment, domain, privacy policy (code ready; see LAUNCH.md)
6. Real job listings and a resume builder
