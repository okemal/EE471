"""Server-only Azure Speech client. Never send credentials to the browser."""

import io
import wave
from xml.etree import ElementTree as ET

import requests


MAX_AUDIO_SECONDS = 60
LANGUAGES = [
    {"id": "en-US", "label": "English (US)"},
    {"id": "en-GB", "label": "English (UK)"},
    {"id": "tr-TR", "label": "Turkish"},
    {"id": "de-DE", "label": "German"},
    {"id": "fr-FR", "label": "French"},
    {"id": "es-ES", "label": "Spanish"},
]


VOICES = [
    {"id": "en-US-JennyNeural", "label": "Jenny · English (US)", "locale": "en-US"},
    {"id": "en-US-GuyNeural", "label": "Guy · English (US)", "locale": "en-US"},
    {"id": "en-GB-SoniaNeural", "label": "Sonia · English (UK)", "locale": "en-GB"},
    {"id": "tr-TR-EmelNeural", "label": "Emel · Turkish", "locale": "tr-TR"},
    {"id": "tr-TR-AhmetNeural", "label": "Ahmet · Turkish", "locale": "tr-TR"},
    {"id": "de-DE-KatjaNeural", "label": "Katja · German", "locale": "de-DE"},
    {"id": "fr-FR-DeniseNeural", "label": "Denise · French", "locale": "fr-FR"},
    {"id": "es-ES-ElviraNeural", "label": "Elvira · Spanish", "locale": "es-ES"},
]


class SpeechError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def azure_request(url, key, **kwargs):
    """Map failures to safe messages; upstream responses can contain private data."""
    headers = kwargs.pop("headers", {})
    headers["Ocp-Apim-Subscription-Key"] = key
    try:
        response = requests.post(url, headers=headers, timeout=(5, 90), **kwargs)
    except requests.Timeout:
        raise SpeechError("Azure took too long to respond. Please try again.", 504) from None
    except requests.RequestException:
        raise SpeechError("Could not reach Azure Speech. Check your connection and try again.", 502) from None
    if response.status_code in (401, 403):
        raise SpeechError("Azure could not authorize this request. Check the server's Speech key and region.", 503)
    if response.status_code == 429:
        raise SpeechError("Azure's request limit was reached. Wait a moment and try again.", 429)
    if not response.ok:
        raise SpeechError("Azure could not process this request. Please try again.", 502)
    return response


def synthesize(text, voice, rate, *, key, region):
    locale = next(item["locale"] for item in VOICES if item["id"] == voice)
    root = ET.Element("speak", version="1.0", attrib={"xml:lang": locale})
    voice_node = ET.SubElement(root, "voice", name=voice)
    # ElementTree escapes user input so it is text, never executable SSML.
    ET.SubElement(voice_node, "prosody", rate=f"{(rate - 1) * 100:+.0f}%").text = text
    response = azure_request(
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        key,
        data=ET.tostring(root, encoding="utf-8"),
        headers={
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm",
            "User-Agent": "EE471-Speech-Studio",
        },
    )
    if not response.content.startswith(b"RIFF"):
        raise SpeechError("Azure returned an invalid audio response. Please try again.")
    return response.content


def validate_audio(data):
    """Check the actual WAV structure, not its untrusted extension or MIME type."""
    if not data:
        raise SpeechError("The audio file is empty. Choose a recording with speech.", 400)
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) != (1, 2, 16000, "NONE"):
                raise SpeechError("Audio must be 16 kHz, mono, 16-bit PCM WAV. Upload it through the website to convert it.", 400)
            frames = audio.getnframes()
            if not frames:
                raise SpeechError("The audio file is empty. Choose a recording with speech.", 400)
            if frames > MAX_AUDIO_SECONDS * 16000:
                raise SpeechError("Audio must be 60 seconds or shorter. Trim the recording and try again.", 400)
            samples = audio.readframes(frames)
            if len(samples) != frames * 2:
                raise SpeechError("The audio file is incomplete. Choose a valid recording.", 400)
    except (wave.Error, EOFError, ValueError, OSError, RuntimeError):
        raise SpeechError("Could not read this audio file. Upload a supported audio file through the website.", 400) from None


def transcribe(audio, language, *, key, region):
    response = azure_request(
        f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1",
        key,
        params={"language": language, "format": "simple"},
        data=audio,
        headers={
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
            "Accept": "application/json",
        },
    )
    try:
        result = response.json()
    except ValueError:
        raise SpeechError("Azure returned an unreadable transcript. Please try again.") from None
    if not isinstance(result, dict):
        raise SpeechError("Azure returned an unreadable transcript. Please try again.")
    status = result.get("RecognitionStatus")
    if status in ("NoMatch", "InitialSilenceTimeout", "BabbleTimeout"):
        raise SpeechError("No clear speech was recognized. Check the language, speak clearly, and try a shorter recording.", 422)
    text = result.get("DisplayText")
    if status != "Success" or not isinstance(text, str):
        raise SpeechError("Azure could not transcribe this recording. Please try again.")
    if not text.strip():
        raise SpeechError("No clear speech was recognized. Try recording again.", 422)
    return text.strip()
