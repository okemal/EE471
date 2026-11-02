"""Azure Speech access. Subscription credentials never leave this module."""

import io
import json
import os
import re
import wave
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


class SpeechError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def azure_request(service, path, body, content_type, extra_headers=None):
    key = os.getenv("AZURE_API_KEY_1") or os.getenv("AZURE_SPEECH_KEY")
    region = os.getenv("AZURE_SPEECH_REGION", "").strip()
    if not key or not re.fullmatch(r"[a-z0-9-]+", region):
        raise SpeechError("Azure Speech is not configured on the server.", 503)
    headers = {"Ocp-Apim-Subscription-Key": key, "Content-Type": content_type}
    headers.update(extra_headers or {})
    request = Request(f"https://{region}.{service}.speech.microsoft.com/{path}",
                      data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=20) as response:
            return response.read()
    except HTTPError as error:
        # Azure response bodies and request objects must never reach the client/logs.
        error.close()
        raise SpeechError("Azure Speech could not complete the request. Try again.") from None
    except (URLError, TimeoutError, OSError):
        raise SpeechError("Azure Speech is unavailable. Try again.") from None


def recognize(audio):
    try:
        with wave.open(io.BytesIO(audio), "rb") as recording:
            if (recording.getnchannels() != 1 or recording.getsampwidth() != 2
                    or recording.getframerate() != 16000
                    or not 0 < recording.getnframes() <= 16000 * 12
                    or len(recording.readframes(recording.getnframes()))
                    != recording.getnframes() * 2):
                raise ValueError
    except (wave.Error, EOFError, ValueError):
        raise SpeechError("Send up to 12 seconds of mono 16 kHz PCM WAV audio.", 400) from None
    raw = azure_request(
        "stt", "speech/recognition/conversation/cognitiveservices/v1?language=en-US&format=detailed",
        audio, "audio/wav; codecs=audio/pcm; samplerate=16000")
    try:
        data = json.loads(raw)
        if data.get("RecognitionStatus") != "Success":
            raise SpeechError("No speech recognized. Tap the microphone and try again.", 422)
        # Lexical form preserves digit command words rather than normalized prose.
        text = data["NBest"][0]["Lexical"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError
        return text
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise SpeechError("Azure Speech returned an invalid response. Try again.") from None


def synthesize(text):
    if (not isinstance(text, str) or not text.strip() or len(text) > 200
            or not re.fullmatch(r"[a-zA-Z0-9 .,+−%*/=\-]+", text)):
        raise SpeechError("Provide a short calculator announcement.", 400)
    ssml = ("<speak version='1.0' xml:lang='en-US'>"
            "<voice name='en-US-JennyNeural'>"
            f"{escape(text)}</voice></speak>")
    return azure_request(
        "tts", "cognitiveservices/v1", ssml.encode(), "application/ssml+xml",
        {"X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
         "User-Agent": "EE471-Voice-Calculator"})
