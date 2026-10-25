"""
Password reset links.

A reset link carries a signed token: the user's id plus a short
fingerprint of their current password hash, signed with SECRET_KEY.

- Signed: nobody can forge or edit a token without SECRET_KEY.
- Expires: tokens older than PASSWORD_RESET_MAX_AGE are rejected.
- Single use: once the password changes, the fingerprint no longer
  matches, so the same link (and every older link) stops working.

The same fingerprint is stored in the login session, which is how
changing your password logs out your other devices.
"""

import hashlib

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

RESET_SALT = "password-reset"


def password_fingerprint(password_hash):
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=RESET_SALT)


def make_reset_token(user):
    return _serializer().dumps(
        {"uid": user["id"], "fp": password_fingerprint(user["password"])}
    )


def read_reset_token(token):
    """Return (user_id, fingerprint), or None if the token is
    invalid, tampered with, or expired."""
    try:
        data = _serializer().loads(
            token, max_age=current_app.config["PASSWORD_RESET_MAX_AGE"]
        )
    except (SignatureExpired, BadSignature):
        return None
    if not isinstance(data, dict) or "uid" not in data or "fp" not in data:
        return None
    return data["uid"], data["fp"]
