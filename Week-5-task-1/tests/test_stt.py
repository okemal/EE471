"""Upload validation and Azure transcription behavior, with no network traffic."""

import io
import json
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse
import wave

import pytest
import requests

from app import create_app


FAKE_KEY = "stt-test-secret-never-display-this"


def wav_bytes(*, frames=1600, sample_rate=16000, channels=1, sample_width=2):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(sample_width)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\0" * (frames * channels * sample_width))
    return buffer.getvalue()


def azure_response(payload, status=200):
    response = requests.Response()
    response.status_code = status
    response._content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    response.headers["Content-Type"] = "application/json"
    return response


@pytest.fixture
def azure_post(monkeypatch):
    post = Mock(return_value=azure_response({
        "RecognitionStatus": "Success", "DisplayText": "Hello from the test.",
    }))
    monkeypatch.setattr("speech.requests.post", post)
    return post


@pytest.fixture
def app(azure_post):
    return create_app({
        "TESTING": True,
        "AZURE_SPEECH_KEY": FAKE_KEY,
        "AZURE_SPEECH_REGION": "westeurope",
    })


@pytest.fixture
def client(app):
    return app.test_client()


def upload(client, audio=None, *, language="en-US", headers=None, filename="recording.wav"):
    data = {"audio": (io.BytesIO(wav_bytes() if audio is None else audio), filename)}
    if language is not None:
        data["language"] = language
    return client.post("/api/speech-to-text", data=data, headers=headers or {})


def test_transcription_sends_audio_and_returns_text_without_credentials(client, azure_post):
    audio = wav_bytes()
    azure_post.return_value = azure_response({
        "RecognitionStatus": "Success", "DisplayText": "Merhaba dünya.",
    })
    response = upload(client, audio, language="tr-TR")

    assert response.status_code == 200
    assert response.json == {"text": "Merhaba dünya.", "language": "tr-TR"}
    assert response.headers["Cache-Control"] == "no-store"
    assert FAKE_KEY not in response.get_data(as_text=True)
    azure_post.assert_called_once()
    args, kwargs = azure_post.call_args
    parsed = urlparse(args[0])
    assert parsed.scheme == "https"
    assert parsed.netloc == "westeurope.stt.speech.microsoft.com"
    assert parsed.path == "/speech/recognition/conversation/cognitiveservices/v1"
    params = {key: values[0] for key, values in parse_qs(parsed.query).items()}
    params.update(kwargs.get("params", {}))
    assert params["language"] == "tr-TR"
    assert params.get("format", "simple") == "simple"
    assert kwargs["data"] == audio
    assert kwargs["headers"]["Ocp-Apim-Subscription-Key"] == FAKE_KEY
    assert "audio/wav" in kwargs["headers"]["Content-Type"]
    assert kwargs["headers"]["Accept"] == "application/json"
    assert all(value > 0 for value in kwargs["timeout"])


@pytest.mark.parametrize("language", [None, "en-US", "en-GB", "tr-TR", "de-DE", "fr-FR", "es-ES"])
def test_supported_languages_and_default(client, language):
    response = upload(client, language=language)
    assert response.status_code == 200
    assert response.json["language"] == (language or "en-US")


@pytest.mark.parametrize("language", ["", "en", "unknown", "en-US&format=detailed", "../en-US"])
def test_invalid_language_never_reaches_azure(client, azure_post, language):
    response = upload(client, language=language)
    assert response.status_code == 400
    assert response.json["error"]
    azure_post.assert_not_called()


@pytest.mark.parametrize("audio", [
    b"", b"not an audio file", b"RIFF" + b"\0" * 40,
    b"RIFF" + (12).to_bytes(4, "little") + b"WAVEJUNK" + (100).to_bytes(4, "little"),
    wav_bytes()[:20], wav_bytes()[:-2], wav_bytes()[:-1],
    wav_bytes(frames=0), wav_bytes(channels=2),
    wav_bytes(sample_rate=44100), wav_bytes(sample_width=1),
    wav_bytes(sample_width=3), wav_bytes(frames=60 * 16000 + 1),
])
def test_invalid_audio_is_rejected_before_azure(client, azure_post, audio):
    response = upload(client, audio)
    assert response.status_code == 400
    assert response.json["error"]
    azure_post.assert_not_called()


def test_sixty_second_audio_is_accepted(client, azure_post):
    response = upload(client, wav_bytes(frames=60 * 16000))
    assert response.status_code == 200
    azure_post.assert_called_once()


@pytest.mark.parametrize("request_kwargs", [
    {"data": {}},
    {"json": {"audio": "pretend.wav"}},
    {"data": {"audio": "pretend.wav"}},
])
def test_missing_file_is_rejected(client, azure_post, request_kwargs):
    response = client.post("/api/speech-to-text", **request_kwargs)
    assert response.status_code == 400
    azure_post.assert_not_called()


def test_oversized_upload_is_rejected(client, azure_post):
    response = upload(client, b"x" * (2 * 1024 * 1024 + 1))
    assert response.status_code == 413
    assert response.is_json
    azure_post.assert_not_called()


@pytest.mark.parametrize("status", ["NoMatch", "InitialSilenceTimeout", "BabbleTimeout"])
def test_no_recognizable_speech_has_actionable_error(client, azure_post, status):
    azure_post.return_value = azure_response({
        "RecognitionStatus": status, "ErrorDetails": FAKE_KEY,
    })
    response = upload(client)
    assert response.status_code == 422
    assert response.json["error"]
    assert FAKE_KEY not in response.get_data(as_text=True)


@pytest.mark.parametrize("text", ["", " \n\t "])
def test_empty_success_is_reported_as_unrecognized_speech(client, azure_post, text):
    azure_post.return_value = azure_response({"RecognitionStatus": "Success", "DisplayText": text})
    response = upload(client)
    assert response.status_code == 422
    assert response.json["error"]


@pytest.mark.parametrize("payload", [
    {"RecognitionStatus": "Error", "ErrorDetails": FAKE_KEY},
    {"RecognitionStatus": "UnknownStatus", "ErrorDetails": FAKE_KEY},
    {}, [], None, "not an object", 42,
    {"RecognitionStatus": "Success"},
    {"RecognitionStatus": "Success", "DisplayText": None},
    {"RecognitionStatus": "Success", "DisplayText": [FAKE_KEY]},
    b"not valid JSON: " + FAKE_KEY.encode(),
])
def test_malformed_or_failed_upstream_result_is_safe(client, azure_post, payload):
    azure_post.return_value = azure_response(payload)
    response = upload(client)
    assert response.status_code == 502
    assert response.json["error"]
    assert FAKE_KEY not in response.get_data(as_text=True)


@pytest.mark.parametrize("upstream_status,expected_status", [
    (401, 503), (403, 503), (429, 429), (400, 502), (500, 502), (503, 502),
])
def test_http_errors_hide_upstream_details(client, azure_post, upstream_status, expected_status):
    azure_post.return_value = azure_response({"error": FAKE_KEY}, status=upstream_status)
    response = upload(client)
    assert response.status_code == expected_status
    assert response.json["error"]
    assert FAKE_KEY not in response.get_data(as_text=True)


@pytest.mark.parametrize("exception,expected_status", [
    (requests.Timeout(FAKE_KEY), 504),
    (requests.ConnectionError(FAKE_KEY), 502),
])
def test_network_errors_are_safe(client, azure_post, exception, expected_status):
    azure_post.side_effect = exception
    response = upload(client)
    assert response.status_code == expected_status
    assert response.json["error"]
    assert FAKE_KEY not in response.get_data(as_text=True)


@pytest.mark.parametrize("overrides", [
    {"AZURE_SPEECH_KEY": ""}, {"AZURE_SPEECH_REGION": ""},
])
def test_unconfigured_server_does_not_call_azure(app, client, azure_post, overrides):
    app.config.update(overrides)
    response = upload(client)
    assert response.status_code == 503
    assert response.json["error"]
    assert FAKE_KEY not in response.get_data(as_text=True)
    assert client.get("/api/health").json == {"configured": False}
    azure_post.assert_not_called()


def test_cross_origin_form_upload_cannot_spend_quota(client, azure_post):
    response = upload(client, headers={"Origin": "https://other.example"})
    assert response.status_code == 403
    azure_post.assert_not_called()


def test_same_origin_upload_is_accepted(client):
    assert upload(client, headers={"Origin": "http://localhost"}).status_code == 200


@pytest.mark.parametrize("path", ["/", "/api/health"])
def test_public_pages_never_expose_key(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert FAKE_KEY not in response.get_data(as_text=True)
    assert "Ocp-Apim-Subscription-Key" not in response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
