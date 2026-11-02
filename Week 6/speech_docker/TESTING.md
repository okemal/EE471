# Verification record

Verified on 2026-11-02 using Docker Desktop's `desktop-linux` context on Linux
amd64, Docker Engine 29.9.2 and Docker Compose v5.6.1. Both runtime images built
successfully using Python 3.11 / Debian Bookworm, Gunicorn 26.2.0 and the pinned,
hash-checked Python dependency files.

Results:

- Studio: **172/172** existing pytest tests passed inside the test image.
- Calculator: **10/10** existing unittest tests passed inside the test image.
- Both backend suites had networking disabled and no credential mounts.
- Configuration helper: **4/4** host unittest tests passed.
- Calculator JavaScript: **5/5** existing Node.js tests passed.
- Both Compose services became healthy; localhost HTTP pages and static
  JavaScript/CSS/audio-worklet resources returned 200.
- All four arithmetic operations, division by zero, invalid operand/operator
  handling, invalid audio/text input and cross-origin POST rejection passed
  through the published HTTP ports.
- Requests for `.env`, secret paths and Python source returned 404.
- Both runtime images started without credentials, served their pages and
  returned safe 503 errors for speech. Secret loading/missing-file behavior,
  non-root UID and read-only source checks passed with no networking.
- Real Azure checks passed for studio WAV synthesis, transcription, continuous
  SDK translation to Turkish and pronunciation assessment, plus calculator
  recognition and MP3 spoken feedback. Only short synthetic test text/audio
  was submitted; no recordings were written to the project.
- The real Gunicorn WebSocket endpoint rejected foreign origins and invalid
  protocol selections. A valid live session streamed synthetic PCM through
  Azure's native SDK, returned a final speaker turn and completed cleanly.
- Running services were verified as UID/GID 10001, with read-only filesystems,
  read-only secret mounts, dropped capabilities, no-new-privileges and ports
  published only on `127.0.0.1`.
- The actual local Speech key was absent from both saved runtime images
  (including decompressed gzip layers), Docker container metadata, logs and
  all non-secret project files. Git ignores the local secret and `.env`.
- All **32 copied source, dependency and test files** that have Week 5
  counterparts matched the originals byte-for-byte. The Week 5 folders were
  not modified.

The final test commands are documented in [README.md](README.md). During
verification, a test-only tmpfs YAML quoting issue was corrected. The WebSocket
probe was also adjusted to include the port in the `Host` header, matching a
browser handshake; `simple-websocket` 1.1's client omitted it. The application's
origin checks were retained. The corrected checks passed.

Physical microphone capture, browser permissions and a real multi-person
diarization session were not tested in this task. The successful streaming
check used one synthetic voice. Container health checks test local HTTP
liveness, not continuing Azure availability or credential validity.
