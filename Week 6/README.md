# Week 6 — Docker Containerization & Cog Model Serving

Deliverables for **EE471 Week 6**, covering multi-container Docker Compose hardening for the Week 5 speech apps and Cog-based model inference for image classification:

1. **Task 1 ([speech_docker/](speech_docker/README.md)) — Dockerized Speech Studio & Voice Calculator**: Self-contained copies of `Week-5-task-1` (port `5000`) and `Week-5-task-2` (port `5001`) behind Gunicorn in non-root (`10001:10001`), read-only containers using Compose file secrets (`/run/secrets/azure_speech_key`).
2. **Task 2 ([cat_id/](cat_id/README.md)) — Felis Cat Family Classifier**: FastAPI web UI (`http://127.0.0.1:8000`) backed by a Cog inference container (`http://127.0.0.1:5002/predictions`) running TorchVision `ResNet50` (`IMAGENET1K_V1`) alongside an `OpenCLIP ViT-B/32` non-cat gate and `BioCLIP 2.5 Huge` species ranker across 41 IUCN CCTF 2017 Felidae profiles.

> **Manual Deliverable Note:** The required screen recordings (`Task-1-demo.avi`, `Task-2-demo.avi`, `Tasks-code-explained.avi`) and interactive clicks in Postman Desktop are manual deliverables. Step-by-step walkthroughs and automated API checks are documented in [cat_id/docs/assignment.md](cat_id/docs/assignment.md) and [speech_docker/README.md](speech_docker/README.md).

## Quick Setup & Verification Commands

### Task 1 (`speech_docker` — Speech Studio & Voice Calculator)

```bash
cd "Week 6/speech_docker"
python3 configure.py --from-env ../../.env   # or --unconfigured for offline page/calculator checks
docker compose up --build -d --wait

# Offline test suites (no credentials or network required)
docker compose -f compose.test.yaml build
docker compose -f compose.test.yaml run --rm studio-tests
docker compose -f compose.test.yaml run --rm calculator-tests
python3 -m unittest discover -s tests -v
node --test voice-calculator/tests/commands.test.mjs

# Live container verification
python3 tests/smoke.py
python3 tests/verify_isolation.py
```

See [speech_docker/README.md](speech_docker/README.md) and [speech_docker/TESTING.md](speech_docker/TESTING.md) for WebSocket probes and recorded verification results.

### Task 2 (`cat_id` — Felis Cat Classifier with Cog)

Allocate at least **10 GiB** of VM memory to Docker Desktop before running CPU BioCLIP + ResNet50 inference.

```bash
cd "Week 6/cat_id"
uv sync --frozen
uv run --frozen pytest -q
node --check frontend/app.js && node --check frontend/ui.js

# Download cached model weights and build the Cog + Web stack
uv run --frozen python scripts/download_models.py
uv run --frozen python scripts/download_resnet.py
cog build --use-cog-base-image=false
docker compose -f compose.cog.yaml build web
docker compose -f compose.cog.yaml up -d --wait --wait-timeout 240

# Verify Cog predictions and browser E2E checks
uv run --frozen python scripts/verify_cog.py
CAT_ID_ARTIFACT_DIR=artifacts/cog/browser uv run --frozen python scripts/check_browser.py
docker compose -f compose.cog.yaml down
```

See [cat_id/README.md](cat_id/README.md), [cat_id/docs/assignment.md](cat_id/docs/assignment.md), and [cat_id/docs/testing.md](cat_id/docs/testing.md) for architecture, Postman payload preparation, taxonomy caveats, and recorded smoke results.
