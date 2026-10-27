"""Exercise live-stream sequencing and cleanup without Azure/network calls."""

import json
import queue
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from simple_websocket import ConnectionClosed

import live_speech
from advanced_speech import sdk_error
from app import create_app


class Socket:
    """A scripted socket that captures decoded server events for assertions.

    Attributes:
        messages: An iterator of client messages or timeout values.
        sent: A list of dicts decoded from server JSON messages.
    """

    def __init__(self, messages):
        """Initializes the client messages that receive will consume.

        Args:
            messages: An iterable of str, bytes, or None client messages.
        """
        self.messages = iter(messages)
        self.sent = []

    def send(self, message):
        """Captures a server JSON message as a Python object.

        Args:
            message: A str JSON message produced by the live-session code.
        """
        self.sent.append(json.loads(message))

    def receive(self, timeout=None):
        """Returns the next scripted message without waiting for real I/O.

        Args:
            timeout: An optional timeout accepted for socket API compatibility.

        Raises:
            StopIteration: The test consumes more messages than it supplied.
        """
        return next(self.messages)


class Session:
    """A synchronous diarization stand-in with observable cleanup state.

    Attributes:
        events: A queue.Queue of client-facing event dicts.
        done: A threading.Event set when fake audio input closes.
        audio: A list of raw PCM byte chunks passed to write.
        stopped: A bool indicating whether cleanup called stop.
    """

    def __init__(self):
        """Initializes empty event, audio, and lifecycle state."""
        self.events = queue.Queue()
        self.done = threading.Event()
        self.audio = []
        self.stopped = False

    def start(self):
        """Accepts startup without creating a native SDK recognizer."""
        pass

    def write(self, data):
        """Records audio and queues interim/final results before input closes.

        Args:
            data: A bytes PCM chunk supplied by the live-session loop.
        """
        self.audio.append(data)
        self.events.put({
            "type": "partial",
            "speaker": "Unknown",
            "text": "hello"
        })
        self.events.put({
            "type": "final",
            "speaker": "Guest-1",
            "text": "Hello.",
            "offset": 0.2
        })

    def close_input(self):
        """Signals completion immediately so tests never wait for Azure."""
        self.done.set()

    def stop(self):
        """Records that the production cleanup path stopped the session."""
        self.stopped = True


def test_live_results_arrive_before_recording_stops_and_final_is_preserved():
    session = Session()
    socket = Socket([b"\0\0" * 1600, json.dumps({"type": "stop"})])
    live_speech.run_live_session(socket,
                                 key="fake",
                                 region="germanywestcentral",
                                 language="en-US",
                                 session_factory=lambda *args: session)
    assert [message["type"] for message in socket.sent
           ] == ["ready", "partial", "final", "done"]
    assert socket.sent[2]["speaker"] == "Guest-1"
    assert session.audio == [b"\0\0" * 1600]
    assert session.stopped


@pytest.mark.parametrize("message", [
    b"x", b"", b"\0" * 32002, "{invalid",
    json.dumps([]),
    json.dumps({"type": "start"})
])
def test_bad_audio_and_commands_end_session_safely(message):
    session = Session()
    socket = Socket([message])
    live_speech.run_live_session(socket,
                                 key="fake",
                                 region="germanywestcentral",
                                 language="en-US",
                                 session_factory=lambda *args: session)
    assert socket.sent[-1]["type"] == "error"
    assert session.stopped
    assert not session.audio


def test_disconnect_stops_azure_session():
    session = Session()
    socket = Socket([])
    socket.receive = Mock(side_effect=ConnectionClosed())
    live_speech.run_live_session(socket,
                                 key="fake",
                                 region="germanywestcentral",
                                 language="en-US",
                                 session_factory=lambda *args: session)
    assert session.stopped


def test_native_errors_do_not_leak_diagnostics():
    secret = "private-test-key"
    socket = Socket([])
    live_speech.run_live_session(
        socket,
        key=secret,
        region="germanywestcentral",
        language="en-US",
        session_factory=Mock(side_effect=RuntimeError(secret)))
    assert socket.sent[-1]["type"] == "error"
    assert secret not in json.dumps(socket.sent)


@pytest.mark.parametrize("code,status", [
    (live_speech.sdk.CancellationErrorCode.AuthenticationFailure, 503),
    (live_speech.sdk.CancellationErrorCode.Forbidden, 503),
    (live_speech.sdk.CancellationErrorCode.TooManyRequests, 429),
    (live_speech.sdk.CancellationErrorCode.ConnectionFailure, 502),
])
def test_sdk_cancellation_messages_hide_diagnostics(code, status):
    error = sdk_error(
        SimpleNamespace(error_code=code, error_details="private-key"))
    assert error.status == status
    assert "private-key" not in str(error)


@pytest.fixture
def live_route(monkeypatch):
    """Exposes the live route as a callable inside a Flask request context.

    This replaces the WebSocket decorator and session runner, allowing origin
    and handshake tests without a real socket or Azure recognizer.

    Args:
        monkeypatch: The pytest fixture used to replace socket registration.

    Returns:
        A tuple of the Flask app, registered route function, and runner mock.
    """
    handlers = {}

    class FakeSock:
        """A route registrar that captures handlers without a socket upgrade."""

        def __init__(self, app):
            """Accepts a Flask app without registering real socket machinery.

            Args:
                app: The Flask application supplied by the application factory.
            """
            pass

        def route(self, path):
            """Returns a decorator that records the handler for a str path."""

            def register(function):
                """Returns the handler after storing it for direct test calls."""
                handlers[path] = function
                return function

            return register

    monkeypatch.setattr(live_speech, "Sock", FakeSock)
    app = create_app({
        "TESTING": True,
        "AZURE_SPEECH_KEY": "private-key",
        "AZURE_SPEECH_REGION": "germanywestcentral"
    })
    run = Mock()
    monkeypatch.setattr(live_speech, "run_live_session", run)
    return app, handlers["/api/live-diarization"], run


@pytest.mark.parametrize("origin", [None, "null", "https://attacker.invalid"])
def test_live_websocket_rejects_cross_origin_before_start(live_route, origin):
    app, route, run = live_route
    headers = {"Origin": origin} if origin else {}
    with app.test_request_context("/api/live-diarization", headers=headers):
        socket = Socket([])
        route(socket)
    assert socket.sent[0]["type"] == "error"
    run.assert_not_called()


@pytest.mark.parametrize(
    "command",
    [None, [], {}, {
        "type": "start",
        "language": "unknown"
    }, {
        "type": "stop"
    }])
def test_live_websocket_validates_start_message(live_route, command):
    app, route, run = live_route
    with app.test_request_context("/api/live-diarization",
                                  headers={"Origin": "http://localhost"}):
        socket = Socket([json.dumps(command)])
        route(socket)
    assert socket.sent[0]["type"] == "error"
    run.assert_not_called()


def test_live_route_passes_credentials_only_to_server_session(live_route):
    app, route, run = live_route
    with app.test_request_context("/api/live-diarization",
                                  headers={"Origin": "http://localhost"}):
        socket = Socket([json.dumps({"type": "start", "language": "tr-TR"})])
        route(socket)
    run.assert_called_once_with(socket,
                                key="private-key",
                                region="germanywestcentral",
                                language="tr-TR")
    assert not socket.sent


def test_live_idle_timeout_closes_session(monkeypatch):
    times = iter([0, 21])
    monkeypatch.setattr(live_speech.time, "monotonic", lambda: next(times))
    session = Session()
    socket = Socket([])
    live_speech.run_live_session(socket,
                                 key="fake",
                                 region="germanywestcentral",
                                 language="en-US",
                                 session_factory=lambda *args: session)
    assert socket.sent[-1]["type"] == "error"
    assert "microphone" in socket.sent[-1]["error"]
    assert session.stopped


def test_live_wall_time_limit_finalizes_instead_of_abandoning_session(
        monkeypatch):
    times = iter([0, 301])
    monkeypatch.setattr(live_speech.time, "monotonic", lambda: next(times))
    session = Session()
    socket = Socket([None])
    live_speech.run_live_session(socket,
                                 key="fake",
                                 region="germanywestcentral",
                                 language="en-US",
                                 session_factory=lambda *args: session)
    assert [item["type"] for item in socket.sent
           ] == ["ready", "finishing", "done"]
    assert session.stopped


def test_live_audio_byte_limit_is_independent_of_wall_time(monkeypatch):
    monkeypatch.setattr(live_speech, "MAX_LIVE_SECONDS", 1)
    session = Session()
    socket = Socket([b"\0\0" * 16000, b"\0\0" * 16000])
    live_speech.run_live_session(socket,
                                 key="fake",
                                 region="germanywestcentral",
                                 language="en-US",
                                 session_factory=lambda *args: session)
    assert socket.sent[-1]["type"] == "error"
    assert len(session.audio) == 1
    assert session.stopped
