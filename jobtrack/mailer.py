"""
Sends email (currently: password reset links).

On your laptop (no MAIL_SERVER in .env) the email is printed in the
terminal, so you can copy the link without setting up any email service.
In production, set MAIL_SERVER and friends in .env to send real email.
"""

import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app

# Tests read this list to check what would have been sent
outbox = []


def send_email(to, subject, body):
    app = current_app
    message = EmailMessage()
    message["From"] = app.config["MAIL_FROM"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    if app.testing:
        outbox.append(message)
        return

    if not app.config["MAIL_SERVER"]:
        app.logger.warning(
            "MAIL_SERVER not set: printing email instead of sending.\n"
            "----- EMAIL -----\nTo: %s\nSubject: %s\n\n%s\n-----------------",
            to, subject, body,
        )
        return

    try:
        with smtplib.SMTP(app.config["MAIL_SERVER"], app.config["MAIL_PORT"], timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if app.config["MAIL_USERNAME"]:
                smtp.login(app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"])
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError):
        # Never show mail-server errors to the user; log them for you
        app.logger.exception("Could not send email to %s", to)
