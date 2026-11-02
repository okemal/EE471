"""Run via `docker compose exec -T speech-studio python - < tests/websocket_probe.py`.

The normal probe never contacts Azure. Add --live after `python -` for a short
synthetic-audio SDK diarization check that consumes a little Azure quota.
"""

import io
import json
import sys
import time
from urllib.request import Request, urlopen
import wave

from simple_websocket import Client, ConnectionClosed

URL = "ws://127.0.0.1:8000/api/live-diarization"
ORIGIN = "http://127.0.0.1:8000"


class ProbeClient(Client):
    def handshake(self):
        # simple-websocket 1.1's client omits the port from Host. Browsers send
        # it, and the server correctly requires Origin to match that Host.
        self.host = f"{self.host}:{self.port}"
        super().handshake()


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def close(ws):
    try:
        ws.close()
    except ConnectionClosed:
        pass  # Server already sent its close frame after the final event.


def probe():
    for origin, command in [("https://example.invalid", None), (ORIGIN, {"type": "start", "language": "invalid"})]:
        ws = ProbeClient.connect(URL, headers={"Origin": origin})
        try:
            if command:
                ws.send(json.dumps(command))
            event = json.loads(ws.receive(timeout=5))
            check(event.get("type") == "error", "Invalid WebSocket session was accepted")
        finally:
            close(ws)
    print("PASS: Gunicorn WebSocket upgrade, origin and protocol rejection")
    if "--live" not in sys.argv:
        return
    req = Request(ORIGIN + "/api/text-to-speech", data=json.dumps({"text": "Three plus five is eight.", "voice": "en-US-JennyNeural"}).encode(), headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=30) as response:
        with wave.open(io.BytesIO(response.read()), "rb") as audio:
            pcm = audio.readframes(audio.getnframes())
    ws = ProbeClient.connect(URL, headers={"Origin": ORIGIN})
    try:
        ws.send(json.dumps({"type": "start", "language": "en-US"}))
        check(json.loads(ws.receive(timeout=20)).get("type") == "ready", "Live Azure session did not become ready")
        for offset in range(0, len(pcm), 6400):
            ws.send(pcm[offset:offset + 6400])
            time.sleep(0.2)
        ws.send(json.dumps({"type": "stop"}))
        final = False
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            message = ws.receive(timeout=5)
            if message is None:
                continue
            event = json.loads(message)
            check(event.get("type") != "error", "Live Azure session returned an error")
            if event.get("type") == "final" and event.get("text") and event.get("speaker"):
                final = True
            if event.get("type") == "done":
                check(final, "No final speaker turn received")
                print("PASS: real Azure SDK streaming, final speaker turn and clean session completion")
                return
        raise RuntimeError("Live Azure session did not finish")
    finally:
        close(ws)


try:
    probe()
except Exception as error:
    print(f"FAIL: {str(error) if isinstance(error, RuntimeError) else type(error).__name__}", file=sys.stderr)
    sys.exit(1)
