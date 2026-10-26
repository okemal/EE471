# Speech Studio — text to speech

A Flask website that turns text into a playable, downloadable WAV using Azure Speech Services. The key stays on the Python server. Audio is held in memory and is not saved by the app.

## Run locally

Install [uv](https://docs.astral.sh/uv/), then:

```bash
cd Week-5-task-1
uv sync
```

Use the existing repository-root `.env`, or copy `.env.example` to `.env` in this folder. Set `AZURE_SPEECH_REGION` to the region shown for your Speech resource under **Keys and Endpoint** in the Azure portal, and set `AZURE_SPEECH_KEY` to its key. The existing key name `AZURE_API_KEY_1` is also supported. Environment variables override `.env` values. Never commit real credentials.

```bash
uv run flask --app app run --host 127.0.0.1 --port 5000
```

Open <http://127.0.0.1:5000>. Choose a voice, enter up to 3,000 characters, and generate speech. Listen in the browser or download the WAV. The app sends text to Azure for synthesis; Azure usage may consume your resource's quota.

```bash
uv run pytest
```

Tests mock Azure and do not require a key or incur Azure usage. Real conversions require a working Speech resource, its matching region, and internet access. Keep the development server bound to localhost; this exercise does not implement accounts or public hosting.

## API

- `GET /api/health`: reports whether a key and region are configured, never their values.
- `POST /api/text-to-speech`: JSON `{ "text": "Hello", "voice": "en-US-JennyNeural", "rate": 1.0 }`; returns `audio/wav` or JSON `{ "error": "..." }`.

The supported voices are listed in `speech.py`. Azure errors are mapped to safe messages and upstream response bodies are never returned to the browser. User text is XML-escaped before creating SSML.

Reference: [Azure text-to-speech REST API](https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech).
