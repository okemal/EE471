"""Speech tools validate local inputs and sanitize Azure/SDK results."""

import base64
import io
import json
from types import SimpleNamespace
from unittest.mock import Mock
import wave

import pytest
import requests

import advanced_speech
from app import create_app
from speech import SpeechError

KEY = "advanced-test-secret-never-return-this"


def wav_bytes(seconds=0.1):
    """Returns silent mono PCM16 WAV bytes at 16 kHz for the given duration.

    Args:
        seconds: An int or float recording duration in seconds.
    """
    output = io.BytesIO()
    with wave.open(output, "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(16000)
        sound.writeframes(b"\0\0" * int(seconds * 16000))
    return output.getvalue()


def assessment_response(nested=False):
    """Builds a pronunciation response in either supported Azure score format.

    Args:
        nested: A bool selecting nested PronunciationAssessment objects rather
            than the flattened score fields returned by the REST service.

    Returns:
        A dict with fixed aggregate, word, and phoneme scores for assertions.
    """
    scores = {
        "PronScore": 88.5,
        "AccuracyScore": 92.0,
        "FluencyScore": 85.0,
        "CompletenessScore": 100.0
    }
    word_scores = {"AccuracyScore": 92.0, "ErrorType": "Mispronunciation"}
    phoneme_scores = {"AccuracyScore": 81.0}
    word = {
        "Word":
            "Hello",
        "Phonemes": [{
            "Phoneme":
                "h",
            **({
                "PronunciationAssessment": phoneme_scores
            } if nested else phoneme_scores)
        }]
    }
    word.update(
        {"PronunciationAssessment": word_scores} if nested else word_scores)
    best = {"Display": "Hello.", "Words": [word]}
    best.update({"PronunciationAssessment": scores} if nested else scores)
    return {"RecognitionStatus": "Success", "NBest": [best]}


@pytest.fixture
def post(monkeypatch):
    """Returns a POST mock serving assessment data without real Azure requests."""
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps(assessment_response()).encode()
    mocked = Mock(return_value=response)
    monkeypatch.setattr("speech.requests.post", mocked)
    return mocked


@pytest.fixture
def client(post):
    """Returns a Flask client with fake credentials and network mocking active."""
    return create_app({
        "TESTING": True,
        "AZURE_SPEECH_KEY": KEY,
        "AZURE_SPEECH_REGION": "germanywestcentral"
    }).test_client()


def upload(client, path, **fields):
    """Submits a multipart speech-tool request with optional custom audio.

    Args:
        client: A Flask test client.
        path: A str speech-tool route to call.
        **fields: Multipart form fields. audio_bytes, when supplied, replaces
            the default valid WAV and is not included as a text form field.

    Returns:
        The Flask test response for the request.
    """
    audio = fields.pop("audio_bytes", wav_bytes())
    return client.post(path,
                       data={
                           "audio": (io.BytesIO(audio), "recording.wav"),
                           **fields
                       })


@pytest.mark.parametrize("nested", [False, True])
def test_assessment_scores_word_feedback_and_safe_header(client, post, nested):
    post.return_value._content = json.dumps(
        assessment_response(nested)).encode()
    result = upload(client,
                    "/api/pronunciation-assessment",
                    reference_text="Hello & merhaba.",
                    language="en-US")
    assert result.status_code == 200
    assert result.json["scores"] == {
        "overall": 88.5,
        "accuracy": 92.0,
        "fluency": 85.0,
        "completeness": 100.0
    }
    assert result.json["words"] == [{
        "word": "Hello",
        "accuracy": 92.0,
        "error": "Mispronunciation",
        "phonemes": [{
            "phoneme": "h",
            "accuracy": 81.0
        }]
    }]
    arguments = post.call_args.kwargs
    settings = json.loads(
        base64.b64decode(arguments["headers"]["Pronunciation-Assessment"]))
    assert settings["ReferenceText"] == "Hello & merhaba."
    assert settings["EnableMiscue"] is True
    assert settings["GradingSystem"] == "HundredMark"
    assert arguments["params"] == {"language": "en-US", "format": "detailed"}
    assert KEY not in result.get_data(as_text=True)


@pytest.mark.parametrize("fields", [
    {},
    {
        "reference_text": "  "
    },
    {
        "reference_text": "x" * 1001
    },
    {
        "reference_text": "hello\0world"
    },
    {
        "reference_text": "Hello",
        "language": "tr-TR"
    },
    {
        "reference_text": "Hello",
        "audio_bytes": wav_bytes(30.01)
    },
    {
        "reference_text": "Hello",
        "audio_bytes": b"fake WAV"
    },
])
def test_assessment_rejects_bad_input_before_azure(client, post, fields):
    assert upload(client, "/api/pronunciation-assessment",
                  **fields).status_code == 400
    post.assert_not_called()


def test_assessment_accepts_thirty_seconds(client):
    assert upload(client,
                  "/api/pronunciation-assessment",
                  reference_text="Hello",
                  audio_bytes=wav_bytes(30)).status_code == 200


@pytest.mark.parametrize("body,status", [
    ({
        "RecognitionStatus": "NoMatch"
    }, 422),
    ({
        "RecognitionStatus": "InitialSilenceTimeout"
    }, 422),
    ([], 502),
    ({}, 502),
    ({
        "RecognitionStatus": "Success",
        "NBest": []
    }, 502),
    ({
        "RecognitionStatus": "Error",
        "ErrorDetails": KEY
    }, 502),
])
def test_bad_assessment_responses_are_safe(client, post, body, status):
    post.return_value._content = json.dumps(body).encode()
    response = upload(client,
                      "/api/pronunciation-assessment",
                      reference_text="Hello")
    assert response.status_code == status
    assert KEY not in response.get_data(as_text=True)


@pytest.mark.parametrize(
    "value",
    [None, "92", True, -1, 101,
     float("nan"), float("inf")])
def test_invalid_assessment_scores_are_not_displayed(client, post, value):
    body = assessment_response()
    body["NBest"][0]["AccuracyScore"] = value
    post.return_value._content = json.dumps(body).encode()
    assert upload(client,
                  "/api/pronunciation-assessment",
                  reference_text="Hello").status_code == 502


@pytest.mark.parametrize("fields", [
    {
        "target_language": "unknown"
    },
    {
        "target_language": "en"
    },
    {
        "target_language": "tr",
        "language": "unknown"
    },
    {
        "target_language": "tr",
        "audio_bytes": b"not WAV"
    },
])
def test_translation_validation_does_not_start_sdk(client, monkeypatch, fields):
    translate = Mock()
    monkeypatch.setattr("app.translate_speech", translate)
    assert upload(client, "/api/speech-translation",
                  **fields).status_code == 400
    translate.assert_not_called()


def test_translation_route_preserves_source_and_target(client, monkeypatch):
    translate = Mock(
        return_value={
            "text": "Hello.",
            "translation": "Merhaba.",
            "language": "en-US",
            "target_language": "tr"
        })
    monkeypatch.setattr("app.translate_speech", translate)
    response = upload(client,
                      "/api/speech-translation",
                      language="en-US",
                      target_language="tr")
    assert response.status_code == 200
    assert response.json["translation"] == "Merhaba."
    assert translate.call_args.args[1:] == ("en-US", "tr")
    assert translate.call_args.kwargs["key"] == KEY


class Signal:
    """A minimal SDK signal that exposes its registered callback to tests.

    Attributes:
        callback: The callable stored after connect is invoked.
    """

    def connect(self, callback):
        """Stores a callable without starting an SDK event-dispatch thread.

        Args:
            callback: The callable that a test can invoke with a fake event.
        """
        self.callback = callback


@pytest.fixture
def fake_translation(monkeypatch):
    """Replaces native SDK objects with deterministic in-process stand-ins.

    Closing the fake stream emits two translated utterances and a completion
    event once. Tests can replace that behavior to simulate failures.

    Args:
        monkeypatch: The pytest fixture used to replace SDK constructors.

    Returns:
        A tuple of the fake recognizer, stream mock, and configuration mock.
    """
    sdk = advanced_speech.sdk
    recognizer = SimpleNamespace(recognized=Signal(),
                                 canceled=Signal(),
                                 session_stopped=Signal())
    future = SimpleNamespace(get=lambda: None)
    recognizer.start_continuous_recognition_async = Mock(return_value=future)
    recognizer.stop_continuous_recognition_async = Mock(return_value=future)
    stream = Mock()
    closed = False

    def close():
        """Emits the fixed utterances once, including on repeated cleanup calls."""
        nonlocal closed
        if closed:
            return
        closed = True
        for text, translated in [("Hello.", "Merhaba."),
                                 ("Welcome.", "Hoş geldiniz.")]:
            recognizer.recognized.callback(
                SimpleNamespace(result=SimpleNamespace(
                    reason=sdk.ResultReason.TranslatedSpeech,
                    text=text,
                    translations={"tr": translated})))
        recognizer.session_stopped.callback(None)

    stream.close.side_effect = close
    config = Mock()
    monkeypatch.setattr(sdk.translation, "SpeechTranslationConfig",
                        Mock(return_value=config))
    monkeypatch.setattr(sdk.translation, "TranslationRecognizer",
                        Mock(return_value=recognizer))
    monkeypatch.setattr(sdk.audio, "PushAudioInputStream",
                        Mock(return_value=stream))
    monkeypatch.setattr(sdk.audio, "AudioConfig", Mock())
    return recognizer, stream, config


def test_translation_keeps_multiple_utterances_and_strips_wav_header(
        fake_translation):
    recognizer, stream, config = fake_translation
    result = advanced_speech.translate_speech(wav_bytes(),
                                              "en-US",
                                              "tr",
                                              key=KEY,
                                              region="germanywestcentral")
    assert result["text"] == "Hello. Welcome."
    assert result["translation"] == "Merhaba. Hoş geldiniz."
    assert len(result["segments"]) == 2
    assert stream.write.call_args.args[0] == b"\0\0" * 1600
    config.add_target_language.assert_called_once_with("tr")
    recognizer.stop_continuous_recognition_async.assert_called_once()


def test_sdk_failure_is_safe_and_closes_resources(fake_translation):
    recognizer, stream, _ = fake_translation
    recognizer.start_continuous_recognition_async.side_effect = RuntimeError(
        KEY)
    with pytest.raises(SpeechError) as caught:
        advanced_speech.translate_speech(wav_bytes(),
                                         "en-US",
                                         "tr",
                                         key=KEY,
                                         region="germanywestcentral")
    assert caught.value.status == 503
    assert KEY not in str(caught.value)
    stream.close.assert_called()
    recognizer.stop_continuous_recognition_async.assert_called_once()


@pytest.mark.parametrize("path,fields", [
    ("/api/speech-translation", {
        "target_language": "tr"
    }),
    ("/api/pronunciation-assessment", {
        "reference_text": "Hello"
    }),
])
def test_new_routes_require_configuration_and_same_origin(
        client, post, path, fields):
    response = client.post(path,
                           data=fields,
                           headers={"Origin": "https://attacker.invalid"})
    assert response.status_code == 403
    client.application.config["AZURE_SPEECH_KEY"] = ""
    assert upload(client, path, **fields).status_code == 503
    post.assert_not_called()


def test_translation_cancellation_is_safe_and_releases_resources(
        fake_translation):
    recognizer, stream, _ = fake_translation
    stream.close.side_effect = lambda: recognizer.canceled.callback(
        SimpleNamespace(
            reason=advanced_speech.sdk.CancellationReason.Error,
            error_code=advanced_speech.sdk.CancellationErrorCode.
            AuthenticationFailure,
            error_details=KEY,
        ))
    with pytest.raises(SpeechError) as caught:
        advanced_speech.translate_speech(wav_bytes(),
                                         "en-US",
                                         "tr",
                                         key=KEY,
                                         region="germanywestcentral")
    assert caught.value.status == 503
    assert KEY not in str(caught.value)
    recognizer.stop_continuous_recognition_async.assert_called_once()


def test_translation_handles_no_speech(fake_translation):
    recognizer, stream, _ = fake_translation
    stream.close.side_effect = lambda: recognizer.session_stopped.callback(None)
    with pytest.raises(SpeechError) as caught:
        advanced_speech.translate_speech(wav_bytes(),
                                         "en-US",
                                         "tr",
                                         key=KEY,
                                         region="germanywestcentral")
    assert caught.value.status == 422


def test_stream_close_failure_cannot_leak_native_diagnostics(fake_translation):
    _, stream, _ = fake_translation
    stream.close.side_effect = RuntimeError(KEY)
    with pytest.raises(SpeechError) as caught:
        advanced_speech.translate_speech(wav_bytes(),
                                         "en-US",
                                         "tr",
                                         key=KEY,
                                         region="germanywestcentral")
    assert KEY not in str(caught.value)
    assert caught.value.status == 503
