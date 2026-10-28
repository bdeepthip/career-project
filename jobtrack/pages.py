"""
Public information pages: Privacy Policy and Terms.
"""

from flask import Blueprint, render_template

bp = Blueprint("pages", __name__)

LAST_UPDATED = "October 28, 2026"


@bp.route("/privacy")
def privacy():
    return render_template("pages/privacy.html", last_updated=LAST_UPDATED)


@bp.route("/terms")
def terms():
    return render_template("pages/terms.html", last_updated=LAST_UPDATED)
