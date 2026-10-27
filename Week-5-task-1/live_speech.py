"""Streams server-side speaker diarization over a same-origin WebSocket.

SDK callbacks enqueue events; the WebSocket request thread sends them to the
browser. This keeps credentials server-side and avoids concurrent socket writes.
register_live_routes installs the endpoint on an existing Flask application.
"""

import json
import queue
import threading
import time

import azure.cognitiveservices.speech as sdk
from flask import request
from flask_sock import Sock
from simple_websocket import ConnectionClosed

from advanced_speech import sdk_error
from speech import LANGUAGES, SpeechError

MAX_LIVE_SECONDS = 300
PCM_BYTES_PER_SECOND = 32000


class DiarizationSession:
    """An Azure conversation transcriber with queued browser-facing events.

    Call start before writing raw PCM, close_input to finish the last turn,
    and stop during cleanup. SDK lifecycle errors are handled by the caller.

    Attributes:
        events: A queue.Queue of JSON-serializable dicts, bounded to 500 events.
        done: A threading.Event set when Azure stops or the event queue fills.
        input_closed: A bool indicating whether the PCM stream is closed.
        stream: An SDK PushAudioInputStream accepting mono PCM16 at 16 kHz.
        transcriber: The SDK ConversationTranscriber producing speaker turns.
    """

    def __init__(self, key, region, language):
        """Initializes the stream and callbacks without starting recognition.

        Args:
            key: A str Azure subscription key that remains on the server.
            region: A str Azure region identifier matching the key.
            language: A str supported conversation locale, such as en-US.
        """
        self.events = queue.Queue(maxsize=500)
        self.done = threading.Event()
        self.input_closed = False
        config = sdk.SpeechConfig(subscription=key, region=region)
        config.speech_recognition_language = language
        config.set_property(
            sdk.PropertyId.SpeechServiceResponse_DiarizeIntermediateResults,
            "true")
        self.stream = sdk.audio.PushAudioInputStream(
            stream_format=sdk.audio.AudioStreamFormat(
                samples_per_second=16000, bits_per_sample=16, channels=1))
        self.transcriber = sdk.transcription.ConversationTranscriber(
            speech_config=config,
            audio_config=sdk.audio.AudioConfig(stream=self.stream))
        self.transcriber.transcribing.connect(
            lambda event: self.result(event, "partial"))
        self.transcriber.transcribed.connect(
            lambda event: self.result(event, "final"))
        self.transcriber.canceled.connect(self.cancelled)
        self.transcriber.session_stopped.connect(lambda event: self.done.set())

    def emit(self, event):
        """Enqueues an event without blocking an Azure callback thread.

        Sets done if the queue is full so a slow consumer cannot grow memory
        use indefinitely.

        Args:
            event: A JSON-serializable dict describing a client-facing event.
        """
        try:
            self.events.put_nowait(event)
        except queue.Full:
            # A slow/disconnected browser must not create unbounded memory use.
            self.done.set()

    def result(self, event, kind):
        """Queues a nonempty SDK recognition result with a speaker label.

        Offsets and durations are converted from 100-nanosecond ticks to
        seconds. Missing speaker labels become Unknown rather than a name.

        Args:
            event: An SDK conversation transcription event.
            kind: A str event type, either partial or final.
        """
        result = event.result
        if result.text and result.reason != sdk.ResultReason.NoMatch:
            self.emit({
                "type": kind,
                "text": result.text,
                "speaker": result.speaker_id or "Unknown",
                "offset": round(result.offset / 10_000_000, 2),
                "duration": round(result.duration / 10_000_000, 2),
            })

    def cancelled(self, event):
        """Queues any sanitized cancellation error and marks the session done.

        Args:
            event: An SDK conversation transcription cancellation event.
        """
        if event.reason == sdk.CancellationReason.Error:
            self.emit({"type": "error", "error": str(sdk_error(event))})
        self.done.set()

    def start(self):
        """Starts transcription and waits for the SDK startup operation."""
        self.transcriber.start_transcribing_async().get()

    def write(self, data):
        """Writes PCM bytes to an open stream after request-side validation.

        Args:
            data: Raw mono, 16-bit little-endian PCM bytes at 16 kHz, without
                a WAV header. The caller enforces sample and chunk boundaries.
        """
        self.stream.write(data)

    def close_input(self):
        """Closes input once so Azure can finalize pending turns."""
        if not self.input_closed:
            self.input_closed = True
            self.stream.close()

    def stop(self):
        """Closes input and waits for the SDK transcription stop operation."""
        self.close_input()
        self.transcriber.stop_transcribing_async().get()


def run_live_session(ws,
                     *,
                     key,
                     region,
                     language,
                     session_factory=DiarizationSession):
    """Relays PCM input and diarization events for an initialized WebSocket.

    The start handshake has already been validated. This function sends ready,
    accepts raw audio or a JSON stop command, and drains pending results before
    sending done. It enforces time, inactivity, byte, and chunk limits, reports
    safe errors, and attempts to stop the SDK session on every exit path.

    Args:
        ws: A simple_websocket.Server-compatible socket with send and receive.
        key: A str server-side Azure subscription key.
        region: A str Azure region identifier matching the key.
        language: A str supported conversation locale.
        session_factory: A callable accepting key, region, and language as
            positional arguments. Returns a DiarizationSession-compatible
            object; tests supply a fake to avoid Azure requests.

    Raises:
        ConnectionClosed: The client disconnects while an error is being sent.
            The route wrapper handles this without returning diagnostics.
    """
    session = None
    try:
        session = session_factory(key, region, language)
        session.start()
        ws.send(json.dumps({"type": "ready", "max_seconds": MAX_LIVE_SECONDS}))
        started = last_audio = time.monotonic()
        received = 0
        finishing = None
        while True:
            while not session.events.empty():
                ws.send(json.dumps(session.events.get_nowait()))
            if session.done.is_set():
                break
            now = time.monotonic()
            if finishing is not None and now - finishing > 12:
                raise SpeechError(
                    "Azure did not finish the live transcript in time. The "
                    "completed lines are still available.", 504)
            if finishing is None and now - started >= MAX_LIVE_SECONDS:
                session.close_input()
                finishing = now
                ws.send(
                    json.dumps({
                        "type": "finishing",
                        "message": "The five-minute session limit was reached. "
                                   "Finishing your transcript…"
                    }))
            if finishing is None and now - last_audio > 20:
                raise SpeechError(
                    "No microphone audio arrived. Check your microphone and "
                    "start a new session.", 408)
            message = ws.receive(timeout=0.1)
            if message is None:
                continue
            if isinstance(message, bytes):
                if finishing is not None:
                    continue
                if not message or len(message) % 2 or len(message) > 32000:
                    raise SpeechError(
                        "Send mono PCM16 audio in chunks of at most one "
                        "second.", 400)
                received += len(message)
                if received > MAX_LIVE_SECONDS * PCM_BYTES_PER_SECOND:
                    raise SpeechError(
                        "This live session reached its five-minute audio "
                        "limit.", 400)
                session.write(message)
                last_audio = time.monotonic()
            else:
                try:
                    command = json.loads(message)
                except (ValueError, TypeError):
                    raise SpeechError("Invalid live-session message.",
                                      400) from None
                if not isinstance(command,
                                  dict) or command.get("type") != "stop":
                    raise SpeechError("Invalid live-session command.", 400)
                if finishing is None:
                    session.close_input()
                    finishing = time.monotonic()
        # Flush final callbacks queued immediately before session_stopped.
        while not session.events.empty():
            ws.send(json.dumps(session.events.get_nowait()))
        ws.send(json.dumps({"type": "done"}))
    except ConnectionClosed:
        pass
    except SpeechError as error:
        ws.send(json.dumps({"type": "error", "error": str(error)}))
    except Exception:
        try:
            ws.send(
                json.dumps({
                    "type": "error",
                    "error":
                        "The live speech session could not continue. Check the "
                        "server's Azure configuration and try again."
                }))
        except ConnectionClosed:
            pass
    finally:
        if session is not None:
            try:
                session.stop()
            except Exception:
                pass


def register_live_routes(app, configured):
    """Registers the live endpoint and its per-process concurrency controls.

    Sets SOCK_SERVER_OPTIONS and allows at most two concurrent live sessions
    for this registration. Call once per application during app creation.

    Args:
        app: The flask.Flask application receiving the WebSocket route.
        configured: A zero-argument callable returning bool configuration
            readiness without exposing the actual credentials.
    """
    app.config["SOCK_SERVER_OPTIONS"] = {
        "ping_interval": 20,
        "max_message_size": 32768
    }
    sock = Sock(app)
    slots = threading.BoundedSemaphore(2)

    @sock.route("/api/live-diarization")
    def live_diarization(ws):
        """Handles a same-origin connection and validates its start handshake.

        Sends safe error events for rejected origins, configuration, locale,
        or concurrency limits. An acquired session slot is always released.

        Args:
            ws: The simple_websocket.Server for this request.
        """
        acquired = False
        try:
            if request.headers.get("Origin") != request.host_url.rstrip("/"):
                raise SpeechError("Cross-origin live sessions are not allowed.",
                                  403)
            if not configured():
                raise SpeechError(
                    "Add an Azure Speech key and region to the server's .env "
                    "file, then restart the app.", 503)
            message = ws.receive(timeout=10)
            try:
                command = json.loads(message)
            except (ValueError, TypeError):
                raise SpeechError(
                    "Start the live session with a language selection.",
                    400) from None
            if not isinstance(command, dict) or command.get(
                    "type") != "start" or command.get("language") not in [
                        item["id"] for item in LANGUAGES
                    ]:
                raise SpeechError(
                    "Choose a supported language for your live session.", 400)
            acquired = slots.acquire(blocking=False)
            if not acquired:
                raise SpeechError(
                    "Two live sessions are already running. Stop one and try "
                    "again.", 429)
            run_live_session(ws,
                             key=app.config["AZURE_SPEECH_KEY"],
                             region=app.config["AZURE_SPEECH_REGION"],
                             language=command["language"])
        except ConnectionClosed:
            pass
        except SpeechError as error:
            ws.send(json.dumps({"type": "error", "error": str(error)}))
        finally:
            if acquired:
                slots.release()
