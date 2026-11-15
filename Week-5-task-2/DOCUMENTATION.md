# Voice Calculator Documentation

This technical reference covers requirements, Azure configuration, arithmetic and audio behavior, architecture, HTTP API contracts, troubleshooting, and verification scope. See [README.md](README.md) for quick-start commands, the voice command table, and keyboard shortcuts, and [CODE_EXPLANATION.md](CODE_EXPLANATION.md) for a file-by-file code walkthrough.

## 1. Requirements & Azure Configuration

### Requirements

- Python with the dependencies in [`requirements.txt`](requirements.txt) (`Flask`, `python-dotenv`).
- A browser supporting `getUserMedia`, `AudioContext`, `AudioWorkletNode`, JavaScript modules, and `AbortSignal.timeout`.
- A microphone and audio output device (on `http://127.0.0.1:5000` or HTTPS).
- Azure Speech credentials and an internet connection for speech features.
- Node.js with the built-in test runner for the JavaScript tests.

See [README.md](README.md) for installation and startup steps. `app.py` starts Flask's local development server with debug mode disabled.

### Azure Configuration

The server searches for `.env` beginning in `Week-5-task-2` and then moving through its parent directories, loading the first file found. Existing process environment variables take priority over `.env`.

| Variable | Purpose |
| --- | --- |
| `AZURE_API_KEY_1` | Primary Azure Speech subscription key variable. |
| `AZURE_SPEECH_KEY` | Fallback used when `AZURE_API_KEY_1` is absent or empty. |
| `AZURE_SPEECH_REGION` | Region of the Speech resource; used to build the Azure service hostname. |

Do not paste credential values into source code, documentation, browser scripts, or screenshots. `.env` is ignored by Git. Restart Flask after changing `.env` so it loads the updated configuration.

## 2. Speech & Arithmetic Behavior

### Spoken Sequence Examples & Silence Detection

Click the microphone on the left, allow access if prompted, and speak commands from the command table in [README.md](README.md). Click the microphone again to finish early.

| Spoken sequence | Equivalent buttons | Result |
| --- | --- | --- |
| Three plus five is | `3 + 5 =` | `8` |
| Nine over three is | `9 ÷ 3 =` | `3` |
| One point five times two is | `1 . 5 × 2 =` | `3` |
| Four minus nine is | `4 − 9 =` | `-5` |

Recording automatically ends after approximately 1.4 seconds below the sound threshold once sound has been detected, or after a 10-second timer. This uses audio volume rather than language-aware speech detection, so background noise can affect when recording stops.

The whole transcript is checked before commands execute. An unknown word rejects the phrase without applying any commands. If an arithmetic error occurs during a valid sequence, earlier commands remain applied and the remaining commands stop.

### Arithmetic & Announcement Rules

Buttons, keyboard shortcuts ([README.md](README.md)), and voice commands share the same calculator behavior and produce ordered spoken feedback. Starting a microphone recording stops current playback and invalidates older queued announcements.

The calculator evaluates operations in button order (for example, `2 + 3 × 4 =` produces `20`, because choosing multiplication completes `2 + 3`). It does not parse mathematical operator precedence.

The display formats results to 12 significant digits. Input is limited to fewer than 14 existing characters (excluding a minus sign) before another digit can be appended; the decimal point counts toward that length. Number announcements read individual digits (`12.5` becomes “one two point five”). Percent always divides by 100.

## 3. Architecture & Data Flow

```mermaid
sequenceDiagram
    participant User
    participant Browser
    participant Flask
    participant Azure
    User->>Browser: Click microphone and speak
    Browser->>Browser: Capture samples and encode PCM WAV
    Browser->>Flask: POST /api/speech/recognize
    Flask->>Azure: Validated audio with server-held key
    Azure-->>Flask: Detailed recognition result
    Flask-->>Browser: Lexical transcript
    Browser->>Browser: Validate phrase and execute keys in order
    Browser->>Flask: POST /api/calculate when needed
    Flask-->>Browser: Result or arithmetic error
    Browser->>Flask: POST /api/speech/speak for announcements
    Flask->>Azure: SSML with server-held key
    Azure-->>Flask: MP3 audio
    Flask-->>Browser: MP3 audio
    Browser->>User: Display result and play announcements in order
```

Calculator state belongs to each browser page. Flask receives two operands per calculation and creates a `Calculator` instance for that request. The server does not maintain a shared calculator session.

Recordings and returned speech pass through memory; the application does not write them to disk. The browser keeps up to 64 decoded announcements in memory for reuse. Recognition and synthesis responses include `Cache-Control: no-store`. Azure still receives recordings and announcement text to provide the requested services; this describes application storage behavior, not Azure retention policies.

## 4. HTTP API

All routes are relative to the Flask server. Successful API requests use status `200`.

### `GET /`

Renders `templates/index.html` with links to the local CSS and JavaScript files.

### `POST /api/calculate`

Content type: `application/json`.

```json
{"operands": [3, 5], "operator": "+"}
```

Successful response:

```json
{"result": 8.0}
```

The operator must be one of `+`, `-`, `*`, `/`. Exactly two finite JSON numbers are required; booleans are rejected. Invalid input, division by zero, and non-finite results return `400` with an `error` message.

### `POST /api/speech/recognize`

Content type: `audio/wav`. The body is raw audio bytes, not a multipart upload or JSON object.

The server accepts nonempty, mono, 16 kHz, 16-bit PCM WAV audio lasting up to 12 seconds and checks that its declared frames are present. The browser's normal recording timer is 10 seconds; the server's acceptance limit is a separate validation boundary.

Successful response:

```json
{"text": "three plus five is"}
```

Recognition requests use English (`en-US`) and detailed results. The first candidate's `Lexical` field supplies words for the command parser.

### `POST /api/speech/speak`

Content type: `application/json`.

```json
{"text": "is eight"}
```

Returns MP3 bytes with content type `audio/mpeg`. The server accepts a nonblank string of up to 200 characters, restricted to letters, digits, spaces, and the punctuation/operator characters in `synthesize()`'s allowlist. It wraps escaped text in SSML, selects `en-US-JennyNeural`, and requests 24 kHz, 48 kbit/s, mono MP3 output.

### Errors and limits

| Status | Meaning in this application |
| --- | --- |
| `400` | Invalid arithmetic input, audio format, or announcement text. |
| `413` | Request exceeds Flask's global 512 KiB body limit. |
| `422` | Azure did not return a successful speech recognition match. |
| `502` | Azure HTTP/network failure, timeout, or malformed recognition response. |
| `503` | Missing key or missing/invalid region configuration. |

Handled arithmetic and speech errors return `{"error": "message"}`. The global `413` response uses Flask's default error page. Azure response bodies, request objects, and detailed upstream errors are not returned to the browser. Azure requests have a 20-second timeout; browser speech fetches use a 25-second abort timeout.

## 5. Troubleshooting

| Symptom | Action |
| --- | --- |
| Microphone access denied | Allow microphone access in browser site permissions, then retry. |
| Microphone support message | Open through localhost or HTTPS and use a browser with the required audio APIs. |
| Could not start microphone | Check the selected device and whether another application has exclusive access. |
| No speech recognized | Move closer to the microphone and speak an English command after clicking it. |
| Command not understood | Use the command table; ordinary conversational instructions are not supported. |
| Recording ends too early or late | Reduce background noise, avoid long pauses inside a sequence, or finish manually. |
| Speech unavailable / request failed | Check connectivity and the Azure resource's key, region, availability, and quota. |
| No spoken feedback | Check system volume/output and the voice status message. Arithmetic remains usable if speech fails. |
| Cannot divide by zero | Clear the calculator or begin a new number, then enter a valid operation. |

## 6. Verification Scope

See [README.md](README.md) for the test commands.

- **Python (`tests/test_speech.py`)**: 10 `unittest` cases covering arithmetic, WAV validation, recognition responses, synthesis, missing configuration, and sanitized upstream failures. Azure calls are mocked so tests run offline without credentials.
- **JavaScript (`tests/commands.test.mjs`)**: 5 Node.js tests covering command mappings, phrase parsing, rejection, spoken numbers, and WAV encoding.
- **CLI walkthrough (`main.py`)**: Prints `10.0`.
- **Manual integration checks**: Enter `3 + 5 =` and verify `8` plus spoken announcements; clear, click the microphone, and say “three plus five is”; check permission denial, unknown phrases, decimals, and division by zero (requires browser audio and valid Azure credentials).
