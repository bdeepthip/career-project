"""
Resume files: checking an uploaded PDF and sending one back for download.
Resumes live in the database (a host's disk is wiped on every deploy).
"""

import re

from flask import Response

MAX_RESUME_BYTES = 5 * 1024 * 1024


def read_pdf_upload(file_storage):
    """Returns (filename, bytes, None) for a valid PDF, or (None, None, error)."""
    if file_storage is None or not file_storage.filename:
        return None, None, "Choose a PDF file to upload."
    data = file_storage.read(MAX_RESUME_BYTES + 1)
    if len(data) > MAX_RESUME_BYTES:
        return None, None, "That file is over 5 MB. Export a smaller PDF and try again."
    # Check the file's actual contents, not just its name
    if not data.startswith(b"%PDF-"):
        return None, None, "That isn't a PDF. Save your resume as PDF and upload that."
    return safe_filename(file_storage.filename), data, None


def safe_filename(name):
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9 ._()-]", "", name).strip() or "resume"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name[-120:]


def pdf_download(filename, data):
    """Always a download (never shown inline in GAJ's own pages)."""
    return Response(data, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{safe_filename(filename)}"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    })
