"""Exercise the public Flask API without credentials or Azure network calls."""

import io
from unittest.mock import Mock
import wave
from xml.etree import ElementTree as ET

import pytest
import requests

from app import MAX_TEXT_LENGTH, create_app

FAKE_KEY = "test-only-secret-that-must-never-reach-the-browser"


def wav_bytes():
    """Returns a valid 10-millisecond silent PCM WAV for mocked Azure replies."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 160)
    return buffer.getvalue()


def azure_response(status=200, body=None):
    """Builds an HTTP response without contacting Azure.

    Args:
        status: An int upstream HTTP status to simulate.
        body: Optional bytes replacing the default valid WAV payload.

    Returns:
        A requests.Response with the requested status and body.
    """
    response = requests.Response()
    response.status_code = status
    response._content = wav_bytes() if body is None else body
    return response


@pytest.fixture
def azure_post(monkeypatch):
    """Returns a POST mock that prevents real network access in each test."""
    # Prevent every test, including validation tests, from reaching real Azure.
    post = Mock(return_value=azure_response())
    monkeypatch.setattr("speech.requests.post", post)
    return post


@pytest.fixture
def app(azure_post):
    """Returns a Flask app with fake credentials after network mocking is active."""
    return create_app({
        "TESTING": True,
        "AZURE_SPEECH_KEY": FAKE_KEY,
        "AZURE_SPEECH_REGION": "westeurope",
    })


@pytest.fixture
def client(app):
    """Returns an in-process HTTP client without opening a listening socket."""
    return app.test_client()


def test_synthesis_returns_playable_download_and_escapes_user_text(
        client, azure_post):
    text = 'Merhaba! A & B <voice name="evil">hello</voice>.'
    response = client.post("/api/text-to-speech",
                           json={
                               "text": text,
                               "voice": "tr-TR-EmelNeural",
                               "rate": 1.25,
                           })

    assert response.status_code == 200
    assert response.mimetype == "audio/wav"
    assert response.headers[
        "Content-Disposition"] == 'attachment; filename="speech.wav"'
    assert response.headers["Cache-Control"] == "no-store"
    with wave.open(io.BytesIO(response.data)) as audio:
        assert audio.getnframes() > 0

    azure_post.assert_called_once()
    args, kwargs = azure_post.call_args
    assert args[
        0] == "https://westeurope.tts.speech.microsoft.com/cognitiveservices/v1"
    assert kwargs["headers"]["Ocp-Apim-Subscription-Key"] == FAKE_KEY
    assert kwargs["headers"]["Content-Type"] == "application/ssml+xml"
    assert kwargs["headers"][
        "X-Microsoft-OutputFormat"] == "riff-16khz-16bit-mono-pcm"
    assert all(value > 0 for value in kwargs["timeout"])
    ssml = ET.fromstring(kwargs["data"])
    assert ssml.attrib["{http://www.w3.org/XML/1998/namespace}lang"] == "tr-TR"
    assert len(ssml.findall(".//voice")) == 1
    assert ssml.find("voice").attrib["name"] == "tr-TR-EmelNeural"
    assert ssml.find("voice/prosody").text == text
    assert ssml.find("voice/prosody").attrib["rate"] == "+25%"
    assert not list(ssml.find("voice/prosody"))


@pytest.mark.parametrize("payload", [
    None,
    [],
    "hello",
    42,
    True,
    {},
    {
        "text": None
    },
    {
        "text": False
    },
    {
        "text": 123
    },
    {
        "text": []
    },
    {
        "text": ""
    },
    {
        "text": " \n\t "
    },
    {
        "text": "x" * (MAX_TEXT_LENGTH + 1)
    },
    {
        "text": "hello\0world"
    },
    {
        "text": "hello",
        "voice": "<voice>"
    },
    {
        "text": "hello",
        "voice": ["en-US-JennyNeural"]
    },
    {
        "text": "hello",
        "rate": "1.0"
    },
    {
        "text": "hello",
        "rate": True
    },
    {
        "text": "hello",
        "rate": None
    },
    {
        "text": "hello",
        "rate": []
    },
    {
        "text": "hello",
        "rate": 0.74
    },
    {
        "text": "hello",
        "rate": 1.51
    },
    {
        "text": "hello",
        "rate": float("inf")
    },
    {
        "text": "hello",
        "rate": float("nan")
    },
    {
        "text": "hello",
        "rate": 10**400
    },
])
def test_invalid_payloads_are_rejected_before_azure(client, azure_post,
                                                    payload):
    response = client.post("/api/text-to-speech", json=payload)
    assert response.status_code == 400
    assert isinstance(response.json["error"], str)
    azure_post.assert_not_called()


@pytest.mark.parametrize("body,content_type", [
    ('{"text":', "application/json"),
    ("text=hello", "application/x-www-form-urlencoded"),
])
def test_invalid_request_formats(client, azure_post, body, content_type):
    response = client.post("/api/text-to-speech",
                           data=body,
                           content_type=content_type)
    assert response.status_code == 400
    azure_post.assert_not_called()


@pytest.mark.parametrize("rate", [0.75, 1.0, 1.5])
def test_supported_speed_boundaries(client, azure_post, rate):
    response = client.post("/api/text-to-speech",
                           json={
                               "text": "Hello.",
                               "rate": rate
                           })
    assert response.status_code == 200
    azure_post.assert_called_once()


@pytest.mark.parametrize("overrides", [
    {
        "AZURE_SPEECH_KEY": ""
    },
    {
        "AZURE_SPEECH_REGION": ""
    },
    {
        "AZURE_SPEECH_REGION": "https://not-an-azure-region.example"
    },
])
def test_missing_or_invalid_configuration_is_actionable(app, client, azure_post,
                                                        overrides):
    app.config.update(overrides)
    assert client.get("/api/health").json == {"configured": False}
    response = client.post("/api/text-to-speech", json={"text": "Hello."})
    assert response.status_code == 503
    assert ".env" in response.json["error"]
    assert FAKE_KEY not in response.get_data(as_text=True)
    azure_post.assert_not_called()


@pytest.mark.parametrize("upstream_status,expected_status", [
    (401, 503),
    (403, 503),
    (429, 429),
    (400, 502),
    (500, 502),
    (503, 502),
])
def test_upstream_errors_hide_private_details(client, azure_post,
                                              upstream_status, expected_status):
    private_detail = f"Upstream private diagnostic: {FAKE_KEY}"
    azure_post.return_value = azure_response(upstream_status,
                                             private_detail.encode())
    response = client.post("/api/text-to-speech", json={"text": "Hello."})
    assert response.status_code == expected_status
    assert response.is_json
    assert response.json["error"]
    assert FAKE_KEY not in response.get_data(as_text=True)
    assert "Upstream private diagnostic" not in response.get_data(as_text=True)


@pytest.mark.parametrize("exception,expected_status", [
    (requests.Timeout(FAKE_KEY), 504),
    (requests.ConnectionError(FAKE_KEY), 502),
])
def test_network_failures_are_safe(client, azure_post, exception,
                                   expected_status):
    azure_post.side_effect = exception
    response = client.post("/api/text-to-speech", json={"text": "Hello."})
    assert response.status_code == expected_status
    assert response.json["error"]
    assert FAKE_KEY not in response.get_data(as_text=True)


def test_success_status_without_audio_is_not_served_as_wav(client, azure_post):
    azure_post.return_value = azure_response(200,
                                             f"Not audio: {FAKE_KEY}".encode())
    response = client.post("/api/text-to-speech", json={"text": "Hello."})
    assert response.status_code == 502
    assert response.is_json
    assert FAKE_KEY not in response.get_data(as_text=True)


@pytest.mark.parametrize("path", ["/", "/api/health", "/missing"])
def test_public_responses_do_not_expose_configuration(client, path):
    response = client.get(path)
    assert FAKE_KEY not in response.get_data(as_text=True)
    assert "Ocp-Apim-Subscription-Key" not in response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    if path == "/api/health":
        assert response.json == {"configured": True}


@pytest.mark.parametrize(
    "origin",
    ["https://other.example", "null", "http://localhost.evil.example"])
def test_cross_origin_requests_cannot_spend_azure_quota(client, azure_post,
                                                        origin):
    response = client.post("/api/text-to-speech",
                           json={"text": "Hello."},
                           headers={"Origin": origin})
    assert response.status_code == 403
    azure_post.assert_not_called()


def test_same_origin_browser_request_is_allowed(client, azure_post):
    response = client.post("/api/text-to-speech",
                           json={"text": "Hello."},
                           headers={"Origin": "http://localhost"})
    assert response.status_code == 200
    azure_post.assert_called_once()


def test_oversized_request_is_rejected_without_azure(app, client, azure_post):
    response = client.post("/api/text-to-speech",
                           data=b"x" * (app.config["MAX_CONTENT_LENGTH"] + 1),
                           content_type="application/json")
    assert response.status_code == 413
    assert response.is_json
    azure_post.assert_not_called()
