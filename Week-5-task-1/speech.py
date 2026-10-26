"""Server-only Azure Speech client. Never send credentials to the browser."""

from xml.etree import ElementTree as ET

import requests


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
