# Vocal — Speech Studio

A local Flask website for text to speech, transcription, speech translation, scripted pronunciation assessment, and real-time speaker diarization. Azure credentials stay on the Python server.

## Run locally

Install [uv](https://docs.astral.sh/uv/), then:

```bash
cd Week-5-task-1
uv sync
uv run flask --app app run --host 127.0.0.1 --port 5000
```

Open <http://127.0.0.1:5000>. Stop the server with Ctrl+C. Run a single server process for this local exercise; Flask-Sock handles the live WebSocket alongside the HTTP routes. No frontend build or FFmpeg installation is needed.

Use the existing repository-root `.env`, or copy `.env.example` to `.env` in this folder. Set `AZURE_SPEECH_KEY` (the existing `AZURE_API_KEY_1` also works) and `AZURE_SPEECH_REGION`. The supplied resource's region is `germanywestcentral`. Find these values under **Keys and Endpoint** in the Azure portal. Environment variables override project `.env`, which overrides repository `.env`. Restart Flask after changing configuration. Never commit real credentials.

The Azure Speech SDK has native components. On another machine, follow Microsoft's [SDK installation requirements](https://learn.microsoft.com/azure/ai-services/speech-service/quickstarts/setup-platform) for your OS and architecture. The existing REST synthesis/transcription routes and the pronunciation endpoint use HTTP; translation and live diarization use the Python SDK.

## Using the website

### Text to speech

Enter up to 3,000 characters, choose a voice and speed, then generate speech. Listen in the browser or download the WAV. Voices include English, Turkish, German, French, and Spanish.

### Speech tools

Choose a tool, upload a short recording or use **Record your voice**, then select the spoken language. Preview the audio before submitting it.

- **Transcribe audio:** receive an editable transcript in the spoken language. Copy it or download a `.txt` file.
- **Translate speech:** choose a target language and receive both the original transcript and translated text. Target languages are English, Turkish, German, French, Spanish, and Italian. The continuous translation recognizer collects multiple utterances in the uploaded clip, including speech separated by pauses. Copy/download uses the translated text.
- **Assess pronunciation:** enter reference text (up to 1,000 characters), record yourself reading it, and compare the recording with the script. The result shows overall, accuracy, fluency, and completeness scores out of 100. Expand **Word & phoneme feedback** to see accuracy and omissions, insertions, or mispronunciations reported by Azure. Supported assessment locales here are US/UK English, German, French, and Spanish; Azure does not support Turkish pronunciation assessment. Scores describe the submitted recording and reference, not subsequent edits to the transcript. Prosody scoring is not enabled.

| Tool | Upload duration | Microphone auto-stop |
| --- | --- | --- |
| Transcription | 60 seconds | 55 seconds |
| Translation | 60 seconds | 55 seconds |
| Pronunciation assessment | 30 seconds | 25 seconds |

The short-audio transcription and assessment endpoints are intended for short utterances and can finish at a pause. Read a short, continuous passage for assessment. A new audio file, tool, reference, or language selection clears the old result.

The browser accepts files up to 20 MiB and converts them to 16 kHz mono PCM16 WAV before upload. WAV, MP3, M4A, OGG, WebM, and FLAC work when your browser supports their codecs; try WAV or MP3 if decoding fails. The server independently validates WAV format and duration, with a 2 MiB HTTP request limit.

### Live speakers

Choose the conversation language and select **Start live session**. Microphone audio streams in small chunks to Flask, which feeds Azure's `ConversationTranscriber`. Interim text appears while someone is speaking; completed turns include a timestamp and a speaker label. Stop the session to finish the last turn, then copy or download the speaker transcript.

- Labels such as `Guest-1` and `Guest-2` distinguish voices within one session. They do not identify a person by name. Early results can be `Unknown`, and speaker assignments can change or be inaccurate, particularly for short or overlapping speech.
- Sessions are limited to five minutes and two concurrent local sessions. The server enforces both elapsed time and an independent audio-byte limit. Your Azure resource may have a lower concurrency quota.
- Switching tabs stops recording and releases the microphone. Leaving/reloading the page disconnects the session. If a connection fails, completed turns remain available to copy or download.
- The page retains the last transcript until the next session connects successfully or the page reloads. The app does not store live audio or speaker profiles.

Use a recent Chrome, Firefox, Edge, or Safari on `localhost` / `127.0.0.1` or HTTPS, and grant microphone permission. Live capture uses `AudioWorklet`; no Azure key or access token is sent to the browser.

## Credentials and data

Text/audio is sent to Azure when you run a speech tool, generate speech, or start a live session. This uses your Azure resource's quota and requires internet access. The app does not retain inputs or results on the server after processing. Browser downloads are saved only when requested. `.env` files are ignored by Git.

The server escapes synthesis text, validates actual WAV content, rejects cross-origin HTTP submissions and WebSocket sessions, and maps provider errors to safe messages. Raw SDK/Azure diagnostics are not returned to the browser. Responses use `Cache-Control: no-store`. Keep this exercise bound to localhost; it has no accounts or public hosting configuration.

## Tests

```bash
uv run pytest
```

The **172 backend tests** mock Azure and require no credentials or Azure usage. They cover the original synthesis/transcription operations, translation across multiple utterances, both Azure pronunciation response formats, invalid scores and uploads, language/duration limits, streaming protocol validation, timeouts, cleanup, origin checks, and credential non-disclosure.

Live integration checks also verified:

- Azure translation of an English MP3 into Turkish, showing both source and translated text.
- Azure pronunciation assessment with real word/phoneme feedback.
- Real-time Azure diarization of Microsoft's two-speaker sample, producing two speaker labels across seven completed turns. Labels are model predictions, not a guarantee of perfect assignment.
- Chromium microphone → AudioWorklet → WebSocket → Azure → speaker transcript, including finalization and download. Browser microphone checks used simulated input.
- Pending microphone cancellation, successful socket closure, the assessment upload limit, and responsive layouts at mobile/tablet/desktop widths.

## Project structure

- `app.py`: Flask routes, configuration, input validation, and response headers.
- `speech.py`: REST synthesis/transcription client and WAV validation.
- `advanced_speech.py`: continuous SDK translation and REST pronunciation assessment.
- `live_speech.py`: server-only conversation transcriber, bounded live sessions, and WebSocket protocol.
- `templates/`: shared layout and feature panels.
- `static/`: tab controls, speech tools, live capture UI, PCM audio worklet, and styles.
- `tests/`: mocked HTTP, SDK, and streaming tests.
- [Developer guide](docs/DEVELOPMENT.md): module contracts, audio formats, live-session lifecycle, and Google-style documentation/formatting checks.
- [Code walkthrough](docs/CODE_WALKTHROUGH.md): concise explanations of the backend, browser scripts, templates, styling, tests, and configuration blocks.
- [WORKFLOW.md](WORKFLOW.md): the original course exercise's branch sequence and conflict resolution.

## API

| Route | Input | Result |
| --- | --- | --- |
| `GET /api/health` | None | `{ "configured": true }`, without configuration values |
| `POST /api/text-to-speech` | JSON `text`, `voice`, `rate` | `audio/wav` download |
| `POST /api/speech-to-text` | Multipart `audio`, `language` | `text`, `language` |
| `POST /api/speech-translation` | Multipart `audio`, source `language` (for example `en-US`), `target_language` (`tr`, `en`, `de`, `fr`, `es`, `it`) | `text`, `translation`, source/target languages, per-utterance `segments` |
| `POST /api/pronunciation-assessment` | Multipart `audio`, `language`, `reference_text` | Recognized `text`, `scores`, `words` with error/phoneme feedback |
| `WS /api/live-diarization` | Same-origin WebSocket; protocol below | Interim/final speaker turns |

HTTP audio must be mono, 16-bit PCM WAV at 16 kHz. Errors return JSON `{ "error": "..." }` with an appropriate status. Supported voices/locales and limits are defined in the Python modules.

Start a live WebSocket by sending JSON `{ "type": "start", "language": "en-US" }`. Wait for `{ "type": "ready", "max_seconds": 300 }`, then send binary **raw PCM16 little-endian, 16 kHz mono** chunks, with no WAV header. Chunks must contain whole samples and be at most 32,000 bytes. Send JSON `{ "type": "stop" }` to finish; keep the socket open for final results and `done`.

Server events are `ready`, `partial`, `final`, `finishing`, `error`, and `done`. Text events include `text`, `speaker`, and `offset`/`duration` in seconds. Disconnects stop the Azure recognizer. No credentials are part of this protocol.

References: [Azure synthesis REST API](https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech), [short-audio transcription REST API](https://learn.microsoft.com/azure/ai-services/speech-service/rest-speech-to-text-short), [speech translation](https://learn.microsoft.com/azure/ai-services/speech-service/get-started-speech-translation), [real-time diarization](https://learn.microsoft.com/azure/ai-services/speech-service/conversation-transcription), [pronunciation assessment](https://learn.microsoft.com/azure/ai-services/speech-service/how-to-pronunciation-assessment), [supported languages](https://learn.microsoft.com/azure/ai-services/speech-service/language-support).
