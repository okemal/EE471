"""Run with `uv run flask --app app run --host 127.0.0.1 --port 5000`."""

import os
from pathlib import Path
import re

from dotenv import dotenv_values
from flask import Flask, jsonify, render_template, request, Response
from werkzeug.exceptions import HTTPException

from speech import VOICES, SpeechError, synthesize

PROJECT_DIR = Path(__file__).resolve().parent
MAX_TEXT_LENGTH = 3000


def create_app(test_config=None):
    app = Flask(__name__)
    # Environment > project .env > repository .env. Do not log these values.
    settings = {
        **dotenv_values(PROJECT_DIR.parent / ".env"),
        **dotenv_values(PROJECT_DIR / ".env"),
        **os.environ,
    }
    app.config.update(
        AZURE_SPEECH_KEY=settings.get("AZURE_SPEECH_KEY") or settings.get("AZURE_API_KEY_1", ""),
        AZURE_SPEECH_REGION=settings.get("AZURE_SPEECH_REGION") or "",
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    def configured():
        return bool(app.config["AZURE_SPEECH_KEY"] and re.fullmatch(r"[a-z][a-z0-9-]{1,49}", app.config["AZURE_SPEECH_REGION"]))

    @app.before_request
    def same_origin():
        # Reject cross-origin form uploads as well as API calls on this local app.
        if request.method == "POST" and request.headers.get("Origin") not in (None, request.host_url.rstrip("/")):
            return jsonify(error="Cross-origin requests are not allowed."), 403

    @app.after_request
    def secure_response(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "microphone=(self)"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        return response

    @app.errorhandler(SpeechError)
    def speech_error(error):
        return jsonify(error=str(error)), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        if error.code == 413:
            return jsonify(error="The upload is too large. Please choose a smaller file."), 413
        return jsonify(error=error.description), error.code

    @app.get("/")
    def index():
        return render_template("index.html", voices=VOICES, configured=configured(), max_text_length=MAX_TEXT_LENGTH)

    @app.get("/api/health")
    def health():
        return jsonify(configured=configured())

    @app.post("/api/text-to-speech")
    def text_to_speech():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Send a JSON object containing text, voice, and rate."), 400
        text = data.get("text")
        if not isinstance(text, str) or not text.strip():
            return jsonify(error="Enter some text to turn into speech."), 400
        text = text.strip()
        if len(text) > MAX_TEXT_LENGTH:
            return jsonify(error=f"Keep your text to {MAX_TEXT_LENGTH:,} characters or fewer."), 400
        if any(not (char in "\t\n\r" or 0x20 <= ord(char) <= 0xD7FF or 0xE000 <= ord(char) <= 0xFFFD or 0x10000 <= ord(char) <= 0x10FFFF) for char in text):
            return jsonify(error="Text contains unsupported control characters."), 400
        voice = data.get("voice", VOICES[0]["id"])
        if voice not in [item["id"] for item in VOICES]:
            return jsonify(error="Choose one of the available voices."), 400
        rate = data.get("rate", 1.0)
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0.75 <= rate <= 1.5:
            return jsonify(error="Choose a speaking speed between 0.75 and 1.5."), 400
        if not configured():
            return jsonify(error="Add an Azure Speech key and region to the server's .env file, then restart the app."), 503
        audio = synthesize(text, voice, rate, key=app.config["AZURE_SPEECH_KEY"], region=app.config["AZURE_SPEECH_REGION"])
        return Response(audio, mimetype="audio/wav", headers={"Content-Disposition": 'attachment; filename="speech.wav"'})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
