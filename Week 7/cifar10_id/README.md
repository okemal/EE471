# Vision10 — Local CIFAR-10 Image Classifier (Week 7 Task 2)

Vision10 is a local dual-model CIFAR-10 classification web application and [Cog](https://github.com/replicate/cog) inference service built for **EE471 Week 7 — Task 2**. It adapts the Week 6 `cat_id` / Task 1 `garment_id` platform to classify 10 RGB object and animal classes (`plane`, `car`, `bird`, `cat`, `deer`, `dog`, `frog`, `horse`, `ship`, `truck`) side by side using:

- **Baseline (`tutorial-baseline`)**: `TutorialCifarNet` matching the PyTorch CIFAR-10 tutorial convolutional network (SGD `lr=0.001`, batch size `4`, `2` epochs, `62,006` parameters — `55.80%` CIFAR-10 test accuracy).
- **Optimized (`resnet9-adamw-48ch`)**: `CifarResNet9` discovered across 5 hyperparameter optimization (HPO) trials (`AdamW` `lr=0.0025`, weight decay `5e-4`, `CosineAnnealingLR`, batch size `128`, `26` epochs, RandomHorizontalFlip + RandomCrop + Cutout, dropout `0.2`, `3,699,514` parameters — `92.49%` CIFAR-10 test accuracy, `+36.69 pp` over baseline).

All inference runs locally (`CIFAR10_ID_OFFLINE=1` default). Weights are stored as verified `safetensors` archives with SHA-256 checksums, uploaded images are stripped of metadata before prediction, and Cog serves HTTP `/predictions` in a non-root, read-only container with host-loopback SSRF URL rejection.

## Project Structure

- [backend/app/](backend/app/) — FastAPI gateway, image validation/stripping, RGB preprocessing (`prepare_cifar_tensor`), `TutorialCifarNet` + `CifarResNet9` architectures, HPO trainer, Cog HTTP client, and Pydantic schemas
- [run.py](run.py) — Cog `Runner` class exposing `/predictions` with dual-model output, startup SHA-256 verification, bounded base64/data-URI decoding, SSRF rejection, and `/tmp/cifar10-predictions.jsonl` structured logging
- [frontend/](frontend/) — Static editorial UI (`index.html`, `app.js`, `ui.js`, `styles.css`) and local CIFAR-10 test assets under `frontend/assets/`
- [scripts/](scripts/) — GPU/CPU HPO training (`train_models.py`), CIFAR-10 sample asset generator (`generate_assets.py`), Postman payload helper (`prepare_postman.py`), Cog verifier (`verify_cog.py`), and Playwright E2E checks (`check_browser.py`)
- [tests/](tests/) — Automated `pytest` unit/integration suite (`94.55%` total line/branch coverage reported against `fail_under = 85`)
- [docs/](docs/) — Detailed project documentation:
  - [Model & HPO Benchmarks](docs/model.md)
  - [API Reference](docs/api.md)
  - [Architecture & Security](docs/architecture.md)
  - [Testing & Verification](docs/testing.md)
  - [Assignment Mapping](docs/assignment.md)
  - [Postman Collection](docs/postman/Vision10.postman_collection.json)

## Quick Start

### 1. Host Setup & Training

Requires Python `>=3.11,<3.13` and `uv`:

```bash
cd "Week 7/cifar10_id"
uv sync --frozen
```

Optional re-training (weights + benchmarks are already saved in `.cache/models/` and `backend/app/data/benchmark.json`):

```bash
uv run --frozen python scripts/train_models.py --device cuda
uv run --frozen python scripts/generate_assets.py
uv run --frozen python scripts/prepare_postman.py frontend/assets/cat.png
```

Run the host FastAPI app directly without Cog:

```bash
./scripts/start.sh
```

Wait for readiness at `http://127.0.0.1:8001`.

### 2. Containerized Cog + Web Stack

Build the Cog inference image (`vision10-cifar-id:cog`) and CPU web gateway (`vision10-cifar-id:cpu`):

```bash
cd "Week 7/cifar10_id"
cog build --use-cog-base-image=false
docker compose -f compose.cog.yaml build web
docker compose -f compose.cog.yaml up -d --wait --wait-timeout 180
```

- Web UI & FastAPI proxy: `http://127.0.0.1:8001` (proxies `/api/identify` to Cog)
- Direct Cog `/predictions` endpoint: `http://127.0.0.1:5003/predictions`
- Inside-container prediction log stream:

```bash
docker compose -f compose.cog.yaml exec cog tail -f /tmp/cifar10-predictions.jsonl
```

Single-container CPU Compose fallback (without separate Cog container):

```bash
docker compose up -d --build
```

Stop containers when finished:

```bash
docker compose -f compose.cog.yaml down
```

## API & Postman Verification

Generate a base64 `data:image/png;base64,...` Cog request body and test `/predictions` directly or via Postman:

```bash
uv run --frozen python scripts/prepare_postman.py frontend/assets/cat.png
curl -sSf http://127.0.0.1:5003/predictions \
  -H 'Content-Type: application/json' \
  --data-binary @artifacts/postman/request.json
```

Postman GUI users can import [Vision10.postman_collection.json](docs/postman/Vision10.postman_collection.json) and send `POST http://127.0.0.1:5003/predictions`. See [docs/api.md](docs/api.md) for FastAPI and Cog schemas.

## Verification

Run lint, formatting, coverage-enforced tests, and JavaScript syntax checks:

```bash
cd "Week 7/cifar10_id"
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest --cov=backend/app --cov=run --cov-report=term-missing
node --check frontend/app.js && node --check frontend/ui.js
```

Run end-to-end Cog and Playwright browser checks against the live compose stack:

```bash
uv run --frozen python scripts/verify_cog.py
CIFAR10_ID_ARTIFACT_DIR=artifacts/cog/browser uv run --frozen python scripts/check_browser.py
```

See [docs/testing.md](docs/testing.md) for test coverage breakdown, Cog verification results, and container security checks.
