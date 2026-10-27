"""Provides Azure REST synthesis, short transcription, and WAV validation.

Callers validate user input before invoking the Azure clients. Credentials are
used only in server-side request headers; provider diagnostics are converted to
safe SpeechError messages before reaching the browser.
"""

import io
import wave
from xml.etree import ElementTree as ET

import requests

MAX_AUDIO_SECONDS = 60
LANGUAGES = [
    {
        "id": "en-US",
        "label": "English (US)"
    },
    {
        "id": "en-GB",
        "label": "English (UK)"
    },
    {
        "id": "tr-TR",
        "label": "Turkish"
    },
    {
        "id": "de-DE",
        "label": "German"
    },
    {
        "id": "fr-FR",
        "label": "French"
    },
    {
        "id": "es-ES",
        "label": "Spanish"
    },
]

VOICES = [
    {
        "id": "en-US-JennyNeural",
        "label": "Jenny · English (US)",
        "locale": "en-US"
    },
    {
        "id": "en-US-GuyNeural",
        "label": "Guy · English (US)",
        "locale": "en-US"
    },
    {
        "id": "en-GB-SoniaNeural",
        "label": "Sonia · English (UK)",
        "locale": "en-GB"
    },
    {
        "id": "tr-TR-EmelNeural",
        "label": "Emel · Turkish",
        "locale": "tr-TR"
    },
    {
        "id": "tr-TR-AhmetNeural",
        "label": "Ahmet · Turkish",
        "locale": "tr-TR"
    },
    {
        "id": "de-DE-KatjaNeural",
        "label": "Katja · German",
        "locale": "de-DE"
    },
    {
        "id": "fr-FR-DeniseNeural",
        "label": "Denise · French",
        "locale": "fr-FR"
    },
    {
        "id": "es-ES-ElviraNeural",
        "label": "Elvira · Spanish",
        "locale": "es-ES"
    },
]


class SpeechError(Exception):
    """A speech operation failure with a client-safe message and HTTP status.

    Attributes:
        status: An int HTTP status code used by Flask's error handler.
    """

    def __init__(self, message, status=502):
        """Initializes a failure that can be returned to the browser.

        Args:
            message: A str explanation without credentials or raw diagnostics.
            status: An int HTTP status code. Defaults to 502.
        """
        super().__init__(message)
        self.status = status


def azure_request(url, key, **kwargs):
    """Posts to Azure with authentication and sanitized error handling.

    Uses five-second connection and 90-second read timeouts. The subscription
    header always uses key, replacing any caller-provided value.

    Args:
        url: A str Azure Speech endpoint URL built from a validated region.
        key: A str subscription key that must remain on the server.
        **kwargs: Request options accepted by requests.post, such as data,
            params, and a dict of additional headers. Do not supply timeout.

    Returns:
        A requests.Response for a successful upstream request.

    Raises:
        SpeechError: Azure rejects the request, the network fails, or a timeout
            occurs. Authentication failures use 503, throttling uses 429,
            timeouts use 504, and other upstream failures use 502.
    """
    headers = kwargs.pop("headers", {})
    headers["Ocp-Apim-Subscription-Key"] = key
    try:
        response = requests.post(url,
                                 headers=headers,
                                 timeout=(5, 90),
                                 **kwargs)
    except requests.Timeout:
        raise SpeechError("Azure took too long to respond. Please try again.",
                          504) from None
    except requests.RequestException:
        raise SpeechError(
            "Could not reach Azure Speech. Check your connection and try "
            "again.", 502) from None
    if response.status_code in (401, 403):
        raise SpeechError(
            "Azure could not authorize this request. Check the server's "
            "Speech key and region.", 503)
    if response.status_code == 429:
        raise SpeechError(
            "Azure's request limit was reached. Wait a moment and try again.",
            429)
    if not response.ok:
        raise SpeechError(
            "Azure could not process this request. Please try again.", 502)
    return response


def synthesize(text, voice, rate, *, key, region):
    """Synthesizes validated text into downloadable PCM WAV audio.

    User text is XML-escaped before it is included in SSML. The caller must
    validate the text length, XML characters, voice, and speaking rate.

    Args:
        text: A str containing the words to speak.
        voice: A str voice ID from VOICES.
        rate: An int or float speed multiplier between 0.75 and 1.5.
        key: A str Azure subscription key, supplied as a keyword argument.
        region: A str Azure region identifier matching the subscription key.

    Returns:
        WAV bytes containing 16 kHz, mono, 16-bit PCM speech.

    Raises:
        SpeechError: The Azure request fails or the response lacks a RIFF
            header.
    """
    locale = next(item["locale"] for item in VOICES if item["id"] == voice)
    root = ET.Element("speak", version="1.0", attrib={"xml:lang": locale})
    voice_node = ET.SubElement(root, "voice", name=voice)
    # ElementTree escapes user input so it is text, never executable SSML.
    ET.SubElement(voice_node, "prosody",
                  rate=f"{(rate - 1) * 100:+.0f}%").text = text
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
        raise SpeechError(
            "Azure returned an invalid audio response. Please try again.")
    return response.content


def validate_audio(data, max_seconds=MAX_AUDIO_SECONDS):
    """Validates WAV encoding, nonempty frame data, and recording duration.

    Checks the actual audio structure rather than its filename or MIME type.
    The caller is responsible for limiting the total HTTP request size.

    Args:
        data: WAV bytes to validate. Must encode mono, 16-bit PCM at 16 kHz.
        max_seconds: An int or float maximum recording duration in seconds.
            Defaults to MAX_AUDIO_SECONDS.

    Raises:
        SpeechError: The audio is empty, malformed, truncated, incorrectly
            encoded, or longer than max_seconds. Uses HTTP status 400.
    """
    if not data:
        raise SpeechError(
            "The audio file is empty. Choose a recording with speech.", 400)
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            if (audio.getnchannels(),
                    audio.getsampwidth(), audio.getframerate(),
                    audio.getcomptype()) != (1, 2, 16000, "NONE"):
                raise SpeechError(
                    "Audio must be 16 kHz, mono, 16-bit PCM WAV. Upload it "
                    "through the website to convert it.", 400)
            frames = audio.getnframes()
            if not frames:
                raise SpeechError(
                    "The audio file is empty. Choose a recording with speech.",
                    400)
            if frames > max_seconds * 16000:
                raise SpeechError(
                    f"Audio must be {max_seconds} seconds or shorter. Trim "
                    f"the recording and try again.", 400)
            samples = audio.readframes(frames)
            if len(samples) != frames * 2:
                raise SpeechError(
                    "The audio file is incomplete. Choose a valid recording.",
                    400)
    except (wave.Error, EOFError, ValueError, OSError, RuntimeError):
        raise SpeechError(
            "Could not read this audio file. Upload a supported audio file "
            "through the website.", 400) from None


def transcribe(audio, language, *, key, region):
    """Transcribes a validated short recording in its spoken language.

    The short-audio service may end recognition at a pause. This function does
    not translate text or validate the WAV; call validate_audio first.

    Args:
        audio: Validated mono, 16 kHz, 16-bit PCM WAV bytes.
        language: A str supported source locale, such as en-US or tr-TR.
        key: A str Azure subscription key, supplied as a keyword argument.
        region: A str Azure region identifier matching the subscription key.

    Returns:
        A str transcript with surrounding whitespace removed.

    Raises:
        SpeechError: No clear speech is recognized (422), Azure returns an
            invalid result (502), or the upstream request fails.
    """
    response = azure_request(
        f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1",
        key,
        params={
            "language": language,
            "format": "simple"
        },
        data=audio,
        headers={
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
            "Accept": "application/json",
        },
    )
    try:
        result = response.json()
    except ValueError:
        raise SpeechError(
            "Azure returned an unreadable transcript. Please try again."
        ) from None
    if not isinstance(result, dict):
        raise SpeechError(
            "Azure returned an unreadable transcript. Please try again.")
    status = result.get("RecognitionStatus")
    if status in ("NoMatch", "InitialSilenceTimeout", "BabbleTimeout"):
        raise SpeechError(
            "No clear speech was recognized. Check the language, speak "
            "clearly, and try a shorter recording.", 422)
    text = result.get("DisplayText")
    if status != "Success" or not isinstance(text, str):
        raise SpeechError(
            "Azure could not transcribe this recording. Please try again.")
    if not text.strip():
        raise SpeechError(
            "No clear speech was recognized. Try recording again.", 422)
    return text.strip()
