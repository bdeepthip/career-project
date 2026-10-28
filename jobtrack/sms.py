"""
Text-message codes for logging in with a phone number.

Production: Twilio Verify sends and checks the codes (set TWILIO_ACCOUNT_SID,
TWILIO_AUTH_TOKEN and TWILIO_VERIFY_SERVICE_SID). About 6 cents per
successful code in the US; no phone number to rent.

Your laptop (no Twilio settings): GAJ makes the code itself and prints it
in the terminal, like password reset emails. On a production server
without Twilio, phone log-in is simply switched off, so codes never end
up in server logs.

Only US and Canadian numbers (+1) are accepted. Texting is paid per
message, and limiting countries is the standard defence against
"SMS pumping" fraud, where bots request codes to expensive numbers.
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from flask import current_app

from .models import PhoneCode, db

CODE_LIFETIME = timedelta(minutes=10)
MAX_ATTEMPTS = 5
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Tests read this list to see what would have been texted
outbox = []


class SmsError(Exception):
    """The code couldn't be sent; safe to show the message to the user."""


def normalize_phone(raw):
    """'(215) 555-0123', '215.555.0123', '+1 215 555 0123' -> '+12155550123'.
    Returns None for anything that isn't a valid US/Canadian number."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    # North American numbers: area code and exchange can't start with 0 or 1
    if digits[0] in "01" or digits[3] in "01":
        return None
    return "+1" + digits


def display_phone(phone):
    """'+12155550123' -> '(215) 555-0123'"""
    if not phone or len(phone) != 12:
        return phone or ""
    d = phone[2:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}"


def masked_phone(phone):
    """'+12155550123' -> '(•••) •••-0123', for 'we texted ...' messages."""
    return f"(•••) •••-{phone[-4:]}" if phone else ""


def twilio_configured():
    c = current_app.config
    return bool(c.get("TWILIO_ACCOUNT_SID") and c.get("TWILIO_AUTH_TOKEN")
                and c.get("TWILIO_VERIFY_SERVICE_SID"))


def sms_enabled():
    """Phone log-in is offered when Twilio is set up, or when not in production."""
    return twilio_configured() or not current_app.config.get("PRODUCTION")


# ---------- Twilio Verify ----------

def _twilio(path, fields):
    c = current_app.config
    url = f"https://verify.twilio.com/v2/Services/{c['TWILIO_VERIFY_SERVICE_SID']}/{path}"
    auth = base64.b64encode(f"{c['TWILIO_ACCOUNT_SID']}:{c['TWILIO_AUTH_TOKEN']}".encode()).decode()
    request = urllib.request.Request(
        url, data=urllib.parse.urlencode(fields).encode(), method="POST",
        headers={"Authorization": f"Basic {auth}"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode())


# ---------- GAJ's own codes (development) ----------

def _hash(phone, code):
    key = current_app.config["SECRET_KEY"].encode()
    return hmac.new(key, f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def _now():
    return datetime.now(timezone.utc)


# ---------- Public functions ----------

def send_code(phone):
    """Text a 6-digit code to phone (already normalized). Raises SmsError."""
    if twilio_configured():
        try:
            _twilio("Verifications", {"To": phone, "Channel": "sms"})
        except (urllib.error.URLError, OSError, ValueError):
            current_app.logger.exception("Twilio could not send a code to %s", masked_phone(phone))
            raise SmsError("We couldn't send a text right now. Try again in a minute.")
        return

    code = f"{secrets.randbelow(1_000_000):06d}"
    PhoneCode.query.filter_by(phone=phone).delete()  # a new code replaces the old one
    db.session.add(PhoneCode(
        phone=phone, code_hash=_hash(phone, code), attempts=0,
        expires_at=(_now() + CODE_LIFETIME).strftime(TIME_FORMAT),
    ))
    db.session.commit()

    text = f"Your GAJ code is {code}. It expires in 10 minutes."
    if current_app.testing:
        outbox.append((phone, text))
    else:
        current_app.logger.warning("Twilio not set up: printing text instead of sending.\n"
                                   "----- TEXT to %s -----\n%s\n----------------------",
                                   phone, text)


def check_code(phone, code):
    """True if code is the right, unexpired code for phone. Each code works once."""
    code = re.sub(r"\D", "", code or "")
    if len(code) != 6:
        return False

    if twilio_configured():
        try:
            result = _twilio("VerificationCheck", {"To": phone, "Code": code})
        except urllib.error.HTTPError as error:
            if error.code == 404:   # expired, used up, or never sent
                return False
            current_app.logger.exception("Twilio check failed")
            return False
        except (urllib.error.URLError, OSError, ValueError):
            current_app.logger.exception("Twilio check failed")
            return False
        return result.get("status") == "approved"

    row = PhoneCode.query.filter_by(phone=phone).first()
    if row is None:
        return False
    expired = datetime.strptime(row.expires_at, TIME_FORMAT).replace(tzinfo=timezone.utc) < _now()
    if expired or row.attempts >= MAX_ATTEMPTS:
        db.session.delete(row)
        db.session.commit()
        return False
    if hmac.compare_digest(row.code_hash, _hash(phone, code)):
        db.session.delete(row)   # used: can't be replayed
        db.session.commit()
        return True
    row.attempts += 1
    db.session.commit()
    return False
