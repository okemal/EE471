# Vocal — Speech Studio

A local Flask website with two tabs: turn text into a playable, downloadable WAV, or transcribe an audio file / microphone recording into editable text. Both use Azure Speech Services through the Python backend.

## Run locally

Install [uv](https://docs.astral.sh/uv/), then:

```bash
cd Week-5-task-1
uv sync
uv run flask --app app run --host 127.0.0.1 --port 5000
```

Open <http://127.0.0.1:5000>. Stop the server with Ctrl+C.

Use the existing repository-root `.env`, or copy `.env.example` to `.env` in this folder. Set `AZURE_SPEECH_KEY` (the existing `AZURE_API_KEY_1` also works) and `AZURE_SPEECH_REGION`. The supplied resource's region is `germanywestcentral`. Find these values under **Keys and Endpoint** in the Azure portal. Environment variables override project `.env`, which overrides repository `.env`. Restart Flask after changing configuration. Never commit real credentials.

## Using the website

- **Text to speech:** enter up to 3,000 characters, choose a voice and speed, then generate speech. Listen in the browser or download the WAV. Voices include English, Turkish, German, French, and Spanish.
- **Speech to text:** upload a short recording or grant microphone permission and record in the browser. Preview it, choose the spoken language, then transcribe. Review or edit the result, copy it, or download a `.txt` file. This transcribes the spoken language; it does not translate between languages.

Audio is limited to **60 seconds**; microphone recording stops at 55 seconds. The short-audio API is intended for short utterances and can finish recognition at a pause. For long meetings or multiple speakers, use a different Azure transcription API.

The browser accepts audio files up to 20 MiB and converts them to 16 kHz mono PCM16 WAV before upload. WAV, MP3, M4A, OGG, WebM, and FLAC work when your browser supports their codecs; try WAV or MP3 if decoding fails. The server independently validates WAV format and duration, with a 2 MiB request limit. Conversion happens in the browser and needs no FFmpeg installation.

Use a recent Chrome, Firefox, Edge, or Safari. Microphone capture needs `localhost` / `127.0.0.1` or HTTPS and browser permission. Switching away from speech to text stops active recording and releases the microphone.

## Credentials and data

The API key stays on the server. `.env` files are ignored by Git. User text is XML-escaped before synthesis; uploaded filenames and MIME types are not trusted. The app reports safe Azure errors without forwarding upstream diagnostics or credentials.

Text or audio is sent to Azure only when you generate or transcribe. This consumes your Azure resource's quota and requires internet access. The app does not retain inputs or results on the server after processing; browser downloads are saved only when requested. Responses use `Cache-Control: no-store`. Keep this exercise bound to localhost; it has no accounts or public hosting configuration.

## Tests

```bash
uv run pytest
```

Automated backend tests mock Azure, need no real key, and incur no Azure usage. They cover both successful operations, XML escaping, malformed input and WAV files, duration limits, language/voice validation, credential non-disclosure, and upstream failures. Browser checks additionally exercised live Azure synthesis/transcription, MP3 conversion, playback and downloads, editable transcripts, microphone capture/automatic stop, and mobile layouts. Microphone browser checks used Chromium's simulated microphone input.

## Project structure

- `app.py`: Flask application factory, routes, configuration, validation, and response headers.
- `speech.py`: server-only Azure REST client, synthesis SSML, WAV validation, and transcription.
- `templates/index.html`: shared layout with separate feature templates.
- `static/app.js`: accessible tabs; `text-to-speech.js` and `speech-to-text.js`: feature interactions and audio conversion.
- `tests/`: independent tests from both feature branches.
- [WORKFLOW.md](WORKFLOW.md): exercise branch sequence and conflict resolution.

## API

| Route | Input | Result |
| --- | --- | --- |
| `GET /api/health` | None | `{ "configured": true }`, without configuration values |
| `POST /api/text-to-speech` | JSON `{ "text": "Hello", "voice": "en-US-JennyNeural", "rate": 1.0 }` | `audio/wav` download |
| `POST /api/speech-to-text` | Multipart `audio` (PCM16 mono 16 kHz WAV), `language` (for example `en-US` or `tr-TR`) | `{ "text": "Hello.", "language": "en-US" }` |

Errors return JSON `{ "error": "..." }` with an appropriate HTTP status. Supported voices and transcription languages are listed in `speech.py`.

References: [Azure text-to-speech REST API](https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech), [Azure short-audio speech-to-text REST API](https://learn.microsoft.com/azure/ai-services/speech-service/rest-speech-to-text-short).
