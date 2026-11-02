"""Load the runtime secret before importing either Week 5 Flask application."""

import os
from pathlib import Path


def load_speech_key():
    """Read only the mounted key; never include its contents in errors/logs."""
    secret_path = os.environ.get("AZURE_SPEECH_KEY_FILE")
    if secret_path:
        try:
            key = Path(secret_path).read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            raise RuntimeError("Cannot read the mounted Azure Speech key.") from None
        # Both apps understand these names but use different precedence.
        os.environ["AZURE_SPEECH_KEY"] = key
        os.environ["AZURE_API_KEY_1"] = key


load_speech_key()

from app import app  # noqa: E402,F401 -- credentials must be loaded first

# The calculator did not have the studio's origin protection. Apply the same
# policy at the container boundary, before any request can consume Azure quota.
from flask import jsonify, request  # noqa: E402


@app.before_request
def reject_cross_origin_posts():
    if request.method == "POST" and request.headers.get("Origin") not in (
        None, request.host_url.rstrip("/")
    ):
        return jsonify(error="Cross-origin requests are not allowed."), 403


@app.after_request
def private_response(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "microphone=(self)"
    return response
