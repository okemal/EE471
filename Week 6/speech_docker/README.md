# Week 6 — Dockerized speech applications

Self-contained copies of the Week 5 Speech Studio (`Week-5-task-1`) and voice
calculator (`Week-5-task-2`). The originals are unchanged. No frontend build is
needed; microphone capture and playback happen in your browser, so the
containers need no host audio devices or privileged mode.

## Start with Docker Desktop

Run from the repository root:

```bash
cd 'Week 6/speech_docker'
python3 configure.py --from-env ../../.env
docker compose up --build -d --wait
```

The helper reads only `AZURE_SPEECH_KEY` (or the legacy `AZURE_API_KEY_1`) and
`AZURE_SPEECH_REGION` from that file. It never prints the key and does not copy
unrelated credentials. It accepts literal dotenv values, quotes, comments and
optional `export`, without variable expansion or shell execution. It refuses to
overwrite existing configuration unless you pass `--force`.

Alternatively, run `python3 configure.py` to enter the key in a hidden prompt,
or `python3 configure.py --unconfigured` to try the pages and arithmetic without
Azure. Speech operations return a safe 503 response when unconfigured.

- Speech Studio: <http://127.0.0.1:5000>
- Voice calculator: <http://127.0.0.1:5001>

Use these localhost addresses and allow your browser's microphone permission.
Chrome/Edge/Firefox/Safari need a secure context (localhost qualifies). The
studio supports synthesis, transcription, translation, pronunciation assessment
and live speaker diarization. For the calculator, try “three plus five is.”
Speech requires an active Azure Speech resource, internet access and quota.

To change the ports, edit `STUDIO_PORT` and `CALCULATOR_PORT` in the generated
local `.env`. Re-run `docker compose up -d --wait` afterward. The services still
listen on port 8000 inside their separate containers.

```bash
docker compose ps                      # both services should be healthy
docker compose logs --tail=50           # server logs; do not enable credential debugging
docker compose down                    # stop and remove this project's containers/network
docker compose up -d --wait             # start again using the built images
```

After changing credentials/region, use `docker compose up -d --force-recreate
--wait`. Configuration is loaded at startup. `docker compose restart` does not
apply changed Compose environment settings, and recreating ensures a replaced
secret file is remounted. `--force` on the helper resets local port settings to
their defaults.

## Credential handling and runtime restrictions

The helper creates `.secrets/azure_speech_key` and a non-secret `.env` containing
the region and ports. Both are ignored by Git. The `.secrets` directory is mode
0700. The key file is 0444 so the non-root container can read the individually
mounted file: local Compose file secrets are bind mounts and do not portably
remap uid/gid/mode. The protected parent directory restricts ordinary host-user
access. This is a local plaintext secret, not an encrypted secret store.

Compose mounts only that key at `/run/secrets/azure_speech_key`, read-only. The
key is never passed as a build argument, Dockerfile environment variable,
Compose environment value, or browser token. `common/container_app.py` reads it
inside the worker before importing the original app. Credentials necessarily
exist in the server process memory; Docker administrators can access container
secrets. Do not publish the key file or dump the worker environment.

The build context uses an allowlist in `.dockerignore`, and Dockerfiles copy
explicit application/dependency files. Repository `.env` files, local secrets,
virtual environments and Git history cannot enter either build. The runtime
images exclude tests and pytest.

Both services run as UID/GID 10001 with a read-only root filesystem, dropped
Linux capabilities, `no-new-privileges`, a PID limit, memory limits and a bounded
writable `/tmp` tmpfs. Published ports bind only to `127.0.0.1`. These are local
course applications without authentication; keep them bound to localhost.

Gunicorn runs one threaded worker per app. The studio's eight threads allow
live WebSocket sessions alongside HTTP, and one worker preserves its original
process-local two-session limit. The studio keeps its five-minute session
limit; Gunicorn's timeout is 360 seconds. The calculator uses four threads and
a 60-second timeout. The wrapper applies same-origin POST protection and
privacy headers to both apps, including the calculator's speech endpoints.
The original app files are copied unchanged.

Health checks probe local HTTP only. A healthy container means the page is
available; it does **not** prove the Azure key, quota or service is working.
The studio's `/api/health` reports whether configuration is present, without
returning its values or calling Azure.

## Dependencies and builds

Both images use Python 3.11 on Debian Bookworm. The studio installs the native
SDK's runtime libraries: ALSA, OpenSSL, the C++ runtime and CA certificates.
The calculator uses the standard-library REST client, so it does not install
the Speech SDK. See [Microsoft's platform requirements](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/quickstarts/setup-platform),
[Flask-Sock's Gunicorn guidance](https://flask-sock.readthedocs.io/en/latest/web_servers.html)
and [Docker Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/).

The studio's `requirements.lock` is exported from its copied Week 5 `uv.lock`.
The calculator retains its original `requirements.txt`; its lock resolves those
ranges with the shared packages constrained to the studio's locked versions.
Gunicorn is added in `common/requirements.lock`. Test dependencies are separate.
All Python installs enforce pinned versions and SHA-256 hashes. The base image
tag and Debian package repositories can receive updates; use `docker compose
build --pull --no-cache` to rebuild with current base/system packages and rerun
the checks below. BuildKit caches normal rebuilds.

To deliberately regenerate dependency locks, install `uv` and run here:

```bash
uv export --project speech-studio --frozen --no-dev --no-emit-project --no-header -o speech-studio/requirements.lock
uv pip compile voice-calculator/requirements.txt --constraint speech-studio/requirements.lock --python-version 3.11 --generate-hashes -o voice-calculator/requirements.lock
uv pip compile common/requirements.in --python-version 3.11 --generate-hashes -o common/requirements.lock
uv pip compile common/requirements-test.in --python-version 3.11 --generate-hashes -o common/requirements-test.lock
```

## Testing

From this directory, the existing backend suites run inside separate test
images, with no secret mounts and with container networking disabled:

```bash
docker compose -f compose.test.yaml build
docker compose -f compose.test.yaml run --rm studio-tests
docker compose -f compose.test.yaml run --rm calculator-tests
python3 -m unittest discover -s tests -v
node --test voice-calculator/tests/commands.test.mjs
```

The first two commands run 172 studio tests and 10 calculator tests. The local
configuration helper has 4 tests, and the JavaScript suite has 5. Only the
JavaScript tests require Node.js on the host. Runtime use requires only Docker
Desktop; the setup helper and HTTP verification scripts use host Python 3.11+.

With both normal services running:

```bash
python3 tests/smoke.py
docker compose exec -T speech-studio python - < tests/websocket_probe.py
python3 tests/verify_isolation.py
```

These check published pages/assets, arithmetic and error cases, origin
protection, WebSocket upgrade/protocol rejection, private-file access, runtime
restrictions, Git exclusions, and credential absence from Docker metadata,
logs, local source and every saved image layer (including gzip-compressed
layers). The actual local key stays in memory during comparisons and is never
printed. Real-key scans are skipped when configured without a key. If you
change ports, pass `--studio-url` / `--calculator-url` to `smoke.py`.

Check startup and error handling without secrets or internet access:

```bash
docker run --rm -i --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --entrypoint python ee471-speech-studio:week6 - < tests/unconfigured_probe.py
docker run --rm -i --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --entrypoint python ee471-voice-calculator:week6 - < tests/unconfigured_probe.py
```

Optional real Azure tests consume a small amount of quota and send only
synthetic test speech/text:

```bash
python3 tests/smoke.py --live
docker compose exec -T speech-studio python - --live < tests/websocket_probe.py
```

They check real synthesis/transcription, SDK translation, pronunciation
assessment, calculator recognition/feedback and streaming diarization with a
final speaker turn and clean completion. They do not test the physical
microphone or guarantee diarization accuracy with multiple people. A final
manual check is to allow microphone access in each browser page, record a
short phrase and play the response. No test saves recordings to this folder.

See [TESTING.md](TESTING.md) for the results recorded during implementation.
