#!/usr/bin/env python3
"""Exercise the published HTTP services. --live uses a little Azure quota."""

import argparse
import io
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid
import wave


def check(condition, label):
    if not condition:
        raise RuntimeError(label)


def call(base, path, *, data=None, content_type=None, origin=None):
    headers = {}
    if isinstance(data, dict):
        data = json.dumps(data).encode()
        content_type = "application/json"
    if content_type:
        headers["Content-Type"] = content_type
    if origin:
        headers["Origin"] = origin
    req = Request(base + path, data=data, headers=headers)
    try:
        response = urlopen(req, timeout=110)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, response.read()


def multipart(audio, **fields):
    boundary = uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        body.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode())
    body.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; filename="test.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode())
    body.extend(audio)
    body.extend(f'\r\n--{boundary}--\r\n'.encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def run(studio, calculator, live=False):
    key_file = Path(__file__).resolve().parents[1] / ".secrets/azure_speech_key"
    key = key_file.read_bytes().strip() if key_file.exists() else b""
    for base, paths in [
        (studio, ["/", "/static/app.js", "/static/styles.css", "/static/pcm-worklet.js", "/static/live-diarization.js"]),
        (calculator, ["/", "/static/js/calculator.js", "/static/js/speech.js", "/static/js/recorder-worklet.js", "/static/css/style.css"]),
    ]:
        for path in paths:
            status, headers, body = call(base, path)
            check(status == 200 and len(body) > 0, "Page/static resource unavailable")
            check(not key or key not in body, "Credential found in an HTTP response")
            check(headers.get("Cache-Control") == "no-store", "Missing privacy header")
        for path in ["/.env", "/.secrets/azure_speech_key", "/app.py"]:
            check(call(base, path)[0] == 404, "Private server file is publicly accessible")
    for operator, operands, result in [("+", [3, 5], 8), ("-", [3, 5], -2), ("*", [3, 5], 15), ("/", [3, 5], 0.6)]:
        status, _, body = call(calculator, "/api/calculate", data={"operator": operator, "operands": operands})
        check(status == 200 and json.loads(body).get("result") == result, "Arithmetic failed")
    for data in [{"operator": "/", "operands": [3, 0]}, {"operator": "+", "operands": [True, 2]}, {"operator": "**", "operands": [2, 3]}]:
        check(call(calculator, "/api/calculate", data=data)[0] == 400, "Invalid arithmetic was accepted")
    for base, path, data in [
        (studio, "/api/text-to-speech", {"text": "Hello"}),
        (calculator, "/api/speech/speak", {"text": "three"}),
    ]:
        check(call(base, path, data=data, origin="https://example.invalid")[0] == 403, "Cross-origin POST was accepted")
    check(call(studio, "/api/text-to-speech", data={"text": ""})[0] == 400, "Invalid studio input was accepted")
    check(call(calculator, "/api/speech/recognize", data=b"invalid", content_type="audio/wav")[0] == 400, "Invalid recording was accepted")
    print("PASS: published pages/assets, arithmetic, validation, origin protection and private-file checks")
    if not live:
        return
    check(bool(json.loads(call(studio, "/api/health")[2]).get("configured")), "Live checks require configured Azure credentials")
    status, headers, audio = call(studio, "/api/text-to-speech", data={"text": "Three plus five is.", "voice": "en-US-JennyNeural", "rate": 1.0})
    check(status == 200 and headers.get_content_type() == "audio/wav", "Azure studio synthesis failed")
    with wave.open(io.BytesIO(audio), "rb") as recording:
        check((recording.getnchannels(), recording.getsampwidth(), recording.getframerate()) == (1, 2, 16000), "Unexpected Azure audio format")
    for path, fields, expected in [
        ("/api/speech-to-text", {"language": "en-US"}, "text"),
        ("/api/speech-translation", {"language": "en-US", "target_language": "tr"}, "translation"),
        ("/api/pronunciation-assessment", {"language": "en-US", "reference_text": "Three plus five is."}, "scores"),
    ]:
        body, kind = multipart(audio, **fields)
        status, _, response = call(studio, path, data=body, content_type=kind)
        check(status == 200 and bool(json.loads(response).get(expected)), "Azure studio speech operation failed")
    status, _, response = call(calculator, "/api/speech/recognize", data=audio, content_type="audio/wav")
    check(status == 200 and "three" in json.loads(response).get("text", "").lower(), "Azure calculator recognition failed")
    status, headers, response = call(calculator, "/api/speech/speak", data={"text": "is eight"})
    check(status == 200 and headers.get_content_type() == "audio/mpeg" and len(response) > 0, "Azure calculator synthesis failed")
    print("PASS: real Azure synthesis, transcription, SDK translation, assessment and calculator speech")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studio-url", default="http://127.0.0.1:5000")
    parser.add_argument("--calculator-url", default="http://127.0.0.1:5001")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    try:
        run(args.studio_url.rstrip("/"), args.calculator_url.rstrip("/"), args.live)
    except Exception as error:
        # Never dump request objects, response bodies or Azure diagnostics.
        print(f"FAIL: {str(error) if isinstance(error, RuntimeError) else type(error).__name__}", file=sys.stderr)
        sys.exit(1)
