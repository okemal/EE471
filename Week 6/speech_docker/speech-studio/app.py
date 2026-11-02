"""Creates the local Flask application and its speech conversion routes.

Run with ``uv run flask --app app run --host 127.0.0.1 --port 5000`` from the
project directory. Importing this module creates app and reads configuration;
Azure requests begin only when a conversion or live session is requested.
"""

import os
from pathlib import Path
import re

from dotenv import dotenv_values
from flask import Flask, jsonify, render_template, request, Response
from werkzeug.exceptions import HTTPException

from advanced_speech import (
    ASSESSMENT_LANGUAGES,
    MAX_ASSESSMENT_SECONDS,
    MAX_REFERENCE_LENGTH,
    TRANSLATION_LANGUAGES,
    assess_pronunciation,
    translate_speech,
)
from live_speech import MAX_LIVE_SECONDS, register_live_routes
from speech import (LANGUAGES, MAX_AUDIO_SECONDS, VOICES, SpeechError,
                    synthesize, transcribe, validate_audio)

PROJECT_DIR = Path(__file__).resolve().parent
MAX_TEXT_LENGTH = 3000


def create_app(test_config=None):
    """Creates a configured Flask application with HTTP and WebSocket routes.

    Loads repository .env values, then project .env values, then environment
    variables. Explicit test_config entries take precedence over all of them.

    Args:
        test_config: An optional dict of Flask configuration overrides. Tests
            supply fake Azure credentials here rather than editing .env files.

    Returns:
        A flask.Flask application with safe error handlers and speech routes.
    """
    app = Flask(__name__)
    # Environment > project .env > repository .env. Do not log these values.
    settings = {
        **dotenv_values(PROJECT_DIR.parent / ".env"),
        **dotenv_values(PROJECT_DIR / ".env"),
        **os.environ,
    }
    app.config.update(
        AZURE_SPEECH_KEY=settings.get("AZURE_SPEECH_KEY") or
        settings.get("AZURE_API_KEY_1", ""),
        AZURE_SPEECH_REGION=settings.get("AZURE_SPEECH_REGION") or "",
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    def configured():
        """Returns whether a key and valid region syntax are configured."""
        return bool(app.config["AZURE_SPEECH_KEY"] and re.fullmatch(
            r"[a-z][a-z0-9-]{1,49}", app.config["AZURE_SPEECH_REGION"]))

    @app.before_request
    def same_origin():
        """Rejects POST requests carrying a different Origin header.

        Returns:
            None for requests without Origin or with a matching origin;
            otherwise a tuple containing a JSON Flask response and status 403.
        """
        # Reject cross-origin POST submissions before they reach Azure.
        if request.method == "POST" and request.headers.get("Origin") not in (
                None, request.host_url.rstrip("/")):
            return jsonify(error="Cross-origin requests are not allowed."), 403

    @app.after_request
    def secure_response(response):
        """Adds privacy and browser security headers to a response in place.

        Args:
            response: The flask.Response being prepared for the client.

        Returns:
            The same response with no-store and browser security headers.
        """
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "microphone=(self)"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; "
            "form-action 'self'")
        return response

    @app.errorhandler(SpeechError)
    def speech_error(error):
        """Converts a speech failure into JSON without upstream diagnostics.

        Args:
            error: A SpeechError with a client-safe message and HTTP status.

        Returns:
            A tuple of a JSON Flask response and the error's int HTTP status.
        """
        return jsonify(error=str(error)), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        """Converts HTTP failures into the API's JSON error envelope.

        Args:
            error: A werkzeug.exceptions.HTTPException raised during a request.

        Returns:
            A tuple of a JSON Flask response and an int HTTP status. Oversized
            requests receive a specific upload message with status 413.
        """
        if error.code == 413:
            return jsonify(
                error="The upload is too large. Please choose a smaller file."
            ), 413
        return jsonify(error=error.description), error.code

    @app.get("/")
    def index():
        """Returns the rendered studio page without exposing credentials."""
        return render_template(
            "index.html",
            voices=VOICES,
            languages=LANGUAGES,
            configured=configured(),
            max_text_length=MAX_TEXT_LENGTH,
            max_audio_seconds=MAX_AUDIO_SECONDS,
            translation_languages=TRANSLATION_LANGUAGES,
            assessment_languages=ASSESSMENT_LANGUAGES,
            max_assessment_seconds=MAX_ASSESSMENT_SECONDS,
            max_reference_length=MAX_REFERENCE_LENGTH,
            max_live_seconds=MAX_LIVE_SECONDS,
        )

    @app.get("/api/health")
    def health():
        """Returns configuration readiness without testing Azure access."""
        return jsonify(configured=configured())

    @app.post("/api/text-to-speech")
    def text_to_speech():
        """Handles POST /api/text-to-speech using text, voice, and rate JSON.

        Returns:
            A flask.Response containing downloadable WAV audio on success, or
            a tuple of a JSON error response and status for invalid input or
            missing configuration.

        Raises:
            SpeechError: Azure synthesis fails; the app error handler converts
                the exception into the API's JSON error response.
        """
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(
                error="Send a JSON object containing text, voice, and rate."
            ), 400
        text = data.get("text")
        if not isinstance(text, str) or not text.strip():
            return jsonify(error="Enter some text to turn into speech."), 400
        text = text.strip()
        if len(text) > MAX_TEXT_LENGTH:
            return jsonify(
                error=
                f"Keep your text to {MAX_TEXT_LENGTH:,} characters or fewer."
            ), 400
        if any(not (char in "\t\n\r" or 0x20 <= ord(char) <= 0xD7FF or 0xE000 <=
                    ord(char) <= 0xFFFD or 0x10000 <= ord(char) <= 0x10FFFF)
               for char in text):
            return jsonify(
                error="Text contains unsupported control characters."), 400
        voice = data.get("voice", VOICES[0]["id"])
        if voice not in [item["id"] for item in VOICES]:
            return jsonify(error="Choose one of the available voices."), 400
        rate = data.get("rate", 1.0)
        if isinstance(rate, bool) or not isinstance(
                rate, (int, float)) or not 0.75 <= rate <= 1.5:
            return jsonify(
                error="Choose a speaking speed between 0.75 and 1.5."), 400
        if not configured():
            return jsonify(
                error=
                "Add an Azure Speech key and region to the server's .env file, "
                "then restart the app."), 503
        audio = synthesize(text,
                           voice,
                           rate,
                           key=app.config["AZURE_SPEECH_KEY"],
                           region=app.config["AZURE_SPEECH_REGION"])
        return Response(audio,
                        mimetype="audio/wav",
                        headers={
                            "Content-Disposition":
                                'attachment; filename="speech.wav"'
                        })

    @app.post("/api/speech-to-text")
    def speech_to_text():
        """Handles POST /api/speech-to-text using a multipart WAV and locale.

        Returns:
            A JSON Flask response containing text and language, or a tuple of
            an error response and status for invalid input or missing setup.

        Raises:
            SpeechError: Audio validation or Azure recognition fails. The app
                error handler converts it into a JSON response.
        """
        language = request.form.get("language", "en-US")
        if language not in [item["id"] for item in LANGUAGES]:
            return jsonify(
                error="Choose one of the available transcription languages."
            ), 400
        upload = request.files.get("audio")
        if upload is None:
            return jsonify(
                error="Choose an audio file or record your voice first."), 400
        audio = upload.read()
        validate_audio(audio)
        if not configured():
            return jsonify(
                error=
                "Add an Azure Speech key and region to the server's .env file, "
                "then restart the app."), 503
        text = transcribe(audio,
                          language,
                          key=app.config["AZURE_SPEECH_KEY"],
                          region=app.config["AZURE_SPEECH_REGION"])
        return jsonify(text=text, language=language)

    def advanced_audio(languages, max_seconds=MAX_AUDIO_SECONDS):
        """Reads and validates an audio upload in the current request context.

        Args:
            languages: A sequence of dicts whose id values are allowed locales.
            max_seconds: An int maximum duration for this operation. Defaults
                to MAX_AUDIO_SECONDS.

        Returns:
            A tuple of validated WAV bytes and the selected str source locale.

        Raises:
            SpeechError: The locale or upload is invalid (400), or Azure
                credentials are not configured (503).
        """
        language = request.form.get("language", "en-US")
        if language not in [item["id"] for item in languages]:
            raise SpeechError(
                "Choose a supported language for this speech tool.", 400)
        upload = request.files.get("audio")
        if upload is None:
            raise SpeechError(
                "Choose an audio file or record your voice first.", 400)
        audio = upload.read()
        validate_audio(audio, max_seconds=max_seconds)
        if not configured():
            raise SpeechError(
                "Add an Azure Speech key and region to the server's .env "
                "file, then restart the app.", 503)
        return audio, language

    @app.post("/api/speech-translation")
    def speech_translation():
        """Handles POST /api/speech-translation using multipart speech input.

        Returns:
            A JSON Flask response with original text, translated text, source
            and target languages, and per-utterance segments.

        Raises:
            SpeechError: Input is invalid, source and target languages match,
                configuration is missing, or Azure translation fails. The app
                error handler serializes the exception.
        """
        target = request.form.get("target_language", "tr")
        if target not in [item["id"] for item in TRANSLATION_LANGUAGES]:
            raise SpeechError("Choose a supported translation language.", 400)
        audio, language = advanced_audio(LANGUAGES)
        if target == language.split("-")[0]:
            raise SpeechError(
                "Choose a translation language different from the spoken "
                "language.", 400)
        return jsonify(
            translate_speech(audio,
                             language,
                             target,
                             key=app.config["AZURE_SPEECH_KEY"],
                             region=app.config["AZURE_SPEECH_REGION"]))

    @app.post("/api/pronunciation-assessment")
    def pronunciation_assessment():
        """Handles POST /api/pronunciation-assessment for a scripted reading.

        Returns:
            A JSON Flask response with recognized text, aggregate scores,
            reference text, and word/phoneme feedback.

        Raises:
            SpeechError: Reference text, locale, or audio is invalid; setup is
                incomplete; or Azure assessment fails. The app error handler
                serializes the exception.
        """
        reference = request.form.get("reference_text", "").strip()
        if not reference or len(reference) > MAX_REFERENCE_LENGTH or any(
                ord(char) < 32 and char not in "\t\n\r" for char in reference):
            raise SpeechError(
                f"Enter reference text between 1 and {MAX_REFERENCE_LENGTH:,} "
                f"characters.", 400)
        audio, language = advanced_audio(ASSESSMENT_LANGUAGES,
                                         MAX_ASSESSMENT_SECONDS)
        return jsonify(
            assess_pronunciation(audio,
                                 language,
                                 reference,
                                 key=app.config["AZURE_SPEECH_KEY"],
                                 region=app.config["AZURE_SPEECH_REGION"]))

    register_live_routes(app, configured)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
