# JobTrack

A job application tracker: log every application, see how your skills
match a job, and let job emails update your application statuses.

## Features

- **Dashboard**: every application with status counts, search and filters
- **Match Score**: compares your profile skills with a job's required skills
- **Match Checker**: paste any job description and get a score
- **Learning plan**: free courses and time estimates for missing skills
- **Accounts**: password reset by email, change password (signs out
  other devices), download all your data, delete your account
- **Inbox**: paste a job email; JobTrack detects Applied / Interview /
  Offer / Rejected, matches the company, and updates the application
  (never moving a status backwards)

## How it works

| Piece | File |
|---|---|
| App setup, security headers, error pages | `jobtrack/__init__.py` |
| Settings (development / production) | `jobtrack/config.py` |
| Database connection per request | `jobtrack/db.py` |
| Tables | `jobtrack/schema.sql` |
| Accounts, password reset, `@login_required` | `jobtrack/auth.py` |
| Account settings, export, deletion | `jobtrack/account.py` |
| Signed, expiring reset tokens | `jobtrack/tokens.py` |
| Outgoing email | `jobtrack/mailer.py` |
| Applications and dashboard | `jobtrack/applications.py` |
| Profile, skills, education, experience | `jobtrack/profile.py` |
| Jobs, job details, Match Checker | `jobtrack/jobs.py` |
| Match Score logic | `jobtrack/matching.py` |
| Inbox routes | `jobtrack/inbox.py` |
| Email status detection and matching | `jobtrack/email_parser.py` |
| Form validation | `jobtrack/validation.py` |

Match Score is keyword-based: it looks for over 40 common technical
skills in a job description and compares them with your profile.
Email status detection is rule-based (phrases like "pleased to offer"
or "not moving forward"), so unusual wording can be missed; the Inbox
lets you fix a match by hand.

## Security

- Passwords stored as salted hashes (Werkzeug)
- CSRF protection on every form (Flask-WTF)
- Every query is parameterized and scoped to the logged-in user;
  tests confirm one user can't see or change another's data
- Server-side validation of all form input, including blocking
  `javascript:` links
- Session cookies are HttpOnly and SameSite=Lax (Secure in production)
- Safe redirects after login; security headers on every response
- Password reset links are signed, expire after 1 hour, and stop
  working once used; the reset page never reveals who has an account
- Changing a password signs out every other device

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

## Tests

```bash
python -m pytest
```

80 tests cover accounts, password reset, data export and deletion, data privacy between users, CSRF, input
validation, Match Score, email parsing and the Inbox.

## Roadmap

1. Foundation: code structure, CSRF, validation, tests (done)
2. Accounts: password reset, account deletion, data export (done)
3. PostgreSQL with migrations
4. A personal email forwarding address for every user
5. Public beta: deployment, domain, privacy policy
6. Real job listings and a resume builder
