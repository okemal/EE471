"""Provides continuous translation and scripted pronunciation assessment.

Credentials and native SDK objects stay on the server. No diagnostic strings
from Azure or the SDK are exposed to clients.
"""

import base64
import io
import json
import math
import threading
import wave

import azure.cognitiveservices.speech as sdk

from speech import LANGUAGES, SpeechError, azure_request

TRANSLATION_LANGUAGES = [
    {
        "id": "tr",
        "label": "Turkish"
    },
    {
        "id": "en",
        "label": "English"
    },
    {
        "id": "de",
        "label": "German"
    },
    {
        "id": "fr",
        "label": "French"
    },
    {
        "id": "es",
        "label": "Spanish"
    },
    {
        "id": "it",
        "label": "Italian"
    },
]
# Turkish isn't supported by Azure pronunciation assessment.
ASSESSMENT_LANGUAGES = [item for item in LANGUAGES if item["id"] != "tr-TR"]
MAX_ASSESSMENT_SECONDS = 30
MAX_REFERENCE_LENGTH = 1000


def pcm_frames(audio):
    """Extracts PCM bytes from an already validated WAV recording.

    Args:
        audio: WAV bytes previously checked by speech.validate_audio.

    Returns:
        Raw PCM bytes without a WAV header, suitable for an SDK push stream.
    """
    with wave.open(io.BytesIO(audio), "rb") as sound:
        return sound.readframes(sound.getnframes())


def sdk_error(event):
    """Maps an SDK cancellation event to a client-safe speech error.

    Args:
        event: An SDK cancellation event with an optional error_code attribute.
            Raw error_details are deliberately ignored.

    Returns:
        A SpeechError instance, not a raised exception. Authentication errors
        map to 503, throttling to 429, and other cancellations to 502.
    """
    code = getattr(event, "error_code", None)
    if code in (sdk.CancellationErrorCode.AuthenticationFailure,
                sdk.CancellationErrorCode.Forbidden):
        return SpeechError(
            "Azure could not authorize this request. Check the server's "
            "Speech key and region.", 503)
    if code == sdk.CancellationErrorCode.TooManyRequests:
        return SpeechError(
            "Azure's request limit was reached. Wait a moment and try again.",
            429)
    return SpeechError(
        "Azure could not complete this speech session. Check your connection "
        "and resource availability, then try again.", 502)


def translate_speech(audio, language, target, *, key, region):
    """Translates all recognized utterances in a validated short recording.

    Continuous recognition preserves utterances separated by pauses. The
    function waits up to 85 seconds for recognition to finish after starting
    the SDK session, then closes the input and stops the recognizer on exit.

    Args:
        audio: Validated mono, 16 kHz, 16-bit PCM WAV bytes, at most 60 seconds.
        language: A str supported source locale, such as en-US.
        target: A str target code from TRANSLATION_LANGUAGES, such as tr.
        key: A str Azure subscription key, supplied as a keyword argument.
        region: A str Azure region identifier matching the subscription key.

    Returns:
        A dict with text, translation, language, target_language, and segments.
        The first two values are str joined utterances; segments is a list of
        dicts containing each original text and its translation.

    Raises:
        SpeechError: No speech is translated (422), recognition times out (504),
            SDK setup fails (503), or Azure cancels the operation with an error.
    """
    done = threading.Event()
    segments = []
    errors = []
    stream = None
    recognizer = None
    try:
        config = sdk.translation.SpeechTranslationConfig(subscription=key,
                                                         region=region)
        config.speech_recognition_language = language
        config.add_target_language(target)
        stream = sdk.audio.PushAudioInputStream(
            stream_format=sdk.audio.AudioStreamFormat(
                samples_per_second=16000, bits_per_sample=16, channels=1))
        recognizer = sdk.translation.TranslationRecognizer(
            translation_config=config,
            audio_config=sdk.audio.AudioConfig(stream=stream))

        def recognized(event):
            """Appends an utterance when Azure supplies text and a translation.

            Args:
                event: An SDK translation recognition event.
            """
            if event.result.reason == sdk.ResultReason.TranslatedSpeech:
                text = event.result.text
                translated = event.result.translations.get(target, "")
                if text and translated:
                    segments.append({"text": text, "translation": translated})

        def cancelled(event):
            """Records a sanitized SDK error and releases the completion wait.

            Args:
                event: An SDK translation cancellation event.
            """
            if event.reason == sdk.CancellationReason.Error:
                errors.append(sdk_error(event))
            done.set()

        recognizer.recognized.connect(recognized)
        recognizer.canceled.connect(cancelled)
        recognizer.session_stopped.connect(lambda event: done.set())
        recognizer.start_continuous_recognition_async().get()
        stream.write(pcm_frames(audio))
        stream.close()
        if not done.wait(85):
            raise SpeechError(
                "Speech translation took too long. Try a shorter recording.",
                504)
        if errors:
            raise errors[0]
        if not segments:
            raise SpeechError(
                "No clear speech was translated. Check the spoken language "
                "and try again.", 422)
        return {
            "text":
                " ".join(segment["text"] for segment in segments),
            "translation":
                " ".join(segment["translation"] for segment in segments),
            "language":
                language,
            "target_language":
                target,
            "segments":
                segments,
        }
    except SpeechError:
        raise
    except Exception:
        raise SpeechError(
            "Could not start Azure speech translation. Check the server's "
            "Speech configuration and SDK installation.", 503) from None
    finally:
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass
        if recognizer is not None:
            try:
                recognizer.stop_continuous_recognition_async().get()
            except Exception:
                pass


def score(value):
    """Normalizes an upstream assessment score without inventing missing data.

    Args:
        value: An object containing a candidate score from an Azure response.

    Returns:
        An int or float in [0, 100], rounded to one decimal place, or None for
        booleans, nonnumeric values, nonfinite numbers, and out-of-range scores.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not 0 <= value <= 100 or not math.isfinite(value):
        return None
    return round(value, 1)


def assess_pronunciation(audio, language, reference, *, key, region):
    """Assesses a validated recording against a supplied reading passage.

    Accepts Azure's flattened and nested pronunciation response formats. The
    caller must validate the locale, reference text, WAV format, and duration.
    Prosody assessment is not enabled.

    Args:
        audio: Validated mono, 16 kHz, 16-bit PCM WAV bytes, at most 30 seconds.
        language: A str locale from ASSESSMENT_LANGUAGES.
        reference: A str reading passage containing between 1 and
            MAX_REFERENCE_LENGTH characters.
        key: A str Azure subscription key, supplied as a keyword argument.
        region: A str Azure region identifier matching the subscription key.

    Returns:
        A dict containing recognized text, language, reference_text, scores,
        and words. Scores contains overall, accuracy, fluency, and completeness
        numbers out of 100. Each word includes its text, accuracy, error label,
        and a list of phonemes; optional detail scores can be None.

    Raises:
        SpeechError: No clear speech is assessed (422), the result is malformed
            or lacks valid aggregate scores (502), or the Azure request fails.
    """
    parameters = {
        "ReferenceText": reference,
        "GradingSystem": "HundredMark",
        "Granularity": "Phoneme",
        "Dimension": "Comprehensive",
        "EnableMiscue": True,
    }
    response = azure_request(
        f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1",
        key,
        params={
            "language": language,
            "format": "detailed"
        },
        data=audio,
        headers={
            "Content-Type":
                "audio/wav; codecs=audio/pcm; samplerate=16000",
            "Accept":
                "application/json",
            "Pronunciation-Assessment":
                base64.b64encode(
                    json.dumps(parameters,
                               ensure_ascii=False).encode()).decode(),
        },
    )
    try:
        result = response.json()
        if result.get("RecognitionStatus") in ("NoMatch",
                                               "InitialSilenceTimeout",
                                               "BabbleTimeout"):
            raise SpeechError(
                "No clear speech was assessed. Read the reference text aloud "
                "and try again.", 422)
        if result.get("RecognitionStatus") != "Success":
            raise ValueError
        best = result["NBest"][0]
        assessment = best.get("PronunciationAssessment", best)
        scores = {
            name: score(assessment.get(field)) for name, field in (
                ("overall", "PronScore"),
                ("accuracy", "AccuracyScore"),
                ("fluency", "FluencyScore"),
                ("completeness", "CompletenessScore"),
            )
        }
        if any(value is None for value in scores.values()):
            raise ValueError
        words = []
        for word in best.get("Words", []):
            detail = word.get("PronunciationAssessment", word)
            error = detail.get("ErrorType", "None")
            words.append({
                "word":
                    str(word["Word"]),
                "accuracy":
                    score(detail.get("AccuracyScore")),
                "error":
                    error if error in ("None", "Omission", "Insertion",
                                       "Mispronunciation") else "Other",
                "phonemes": [{
                    "phoneme":
                        str(item["Phoneme"]),
                    "accuracy":
                        score(
                            item.get("PronunciationAssessment",
                                     item).get("AccuracyScore"))
                } for item in word.get("Phonemes", [])],
            })
        return {
            "text": best.get("Display") or result.get("DisplayText", ""),
            "language": language,
            "reference_text": reference,
            "scores": scores,
            "words": words,
        }
    except SpeechError:
        raise
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise SpeechError(
            "Azure returned an unreadable pronunciation assessment. Please try "
            "again.") from None
