"""Server-only Azure Speech client for short, single-utterance recordings."""

import io
import wave

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
