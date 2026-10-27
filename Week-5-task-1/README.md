# Speech Studio — speech to text

A local Flask website that transcribes a short audio file or microphone recording using Azure Speech Services. Preview your audio, select the spoken language, and copy or download the resulting text.

## Run locally

```bash
cd Week-5-task-1
uv sync
uv run flask --app app run --host 127.0.0.1 --port 5000
```

Open <http://127.0.0.1:5000>. The existing repository-root `.env` is supported. Alternatively, copy `.env.example` to `.env` in this folder. Set `AZURE_SPEECH_REGION` to the resource's region and `AZURE_SPEECH_KEY` (or the existing `AZURE_API_KEY_1`) to its key. Environment variables override project `.env`, which overrides repository `.env`. Never commit credentials. Restart Flask after changing configuration.

## Transcribing

Upload a recording, or grant microphone permission and record directly in the browser. Choose the language actually spoken in the audio, then select **Transcribe**. This transcribes speech; it does not translate between languages. The short-audio API is intended for short utterances, not long meetings, and recognition can end at a pause.

Audio must be at most 60 seconds. Microphone recording stops automatically at 55 seconds. Uploads are limited to 20 MiB in the browser. WAV, MP3, M4A, OGG, WebM, and FLAC are accepted when your browser can decode them. The browser converts audio to 16 kHz mono PCM16 WAV before sending it. The server independently validates WAV format and duration and limits requests to 2 MiB. If a codec is unsupported, use WAV or MP3 instead.

Microphone recording requires a modern browser on `localhost` / `127.0.0.1` or HTTPS. Audio is sent to Azure only when you transcribe it. The app keeps uploads and transcripts in memory and does not save them on the server. Conversion uses Azure quota and requires internet access. This local exercise has no accounts and should remain bound to localhost.

```bash
uv run pytest
```

Tests mock Azure and need no credentials.

## API

- `GET /api/health`: reports configuration readiness without exposing credentials.
- `POST /api/speech-to-text`: multipart form with `audio` (PCM16, mono, 16 kHz WAV, at most 60 seconds) and `language` (for example `en-US` or `tr-TR`). Returns `{ "text": "Hello.", "language": "en-US" }` or `{ "error": "..." }`.

Reference: [Azure speech-to-text REST API for short audio](https://learn.microsoft.com/azure/ai-services/speech-service/rest-speech-to-text-short).
