# Atelier — Local FashionMNIST Garment Classifier (Week 7 Task 1)

Atelier is a local dual-model garment classification web application and [Cog](https://github.com/replicate/cog) inference service built for **EE471 Week 7 — Task 1**. It modifies the Week 6 `cat_id` application to classify 10 FashionMNIST garment categories side by side using:

- **Baseline (`quickstart-baseline`)**: `QuickstartMLP` following the PyTorch Quickstart tutorial (SGD `lr=0.001`, batch size `64`, `5` epochs, `669,706` parameters — `64.28%` FashionMNIST test accuracy).
- **Optimized (`convnet-adamw-64ch`)**: `GarmentConvNet` discovered across 6 structured hyperparameter optimization (HPO) trials (AdamW `lr=0.001`, weight decay `5e-4`, `CosineAnnealingLR`, batch size `64`, `20` epochs, RandomHorizontalFlip + RandomAffine, dropout `0.25`, label smoothing `0.05`, `1,868,746` parameters — `94.61%` FashionMNIST test accuracy, `+30.33 pp` over baseline).

All inference stays local (`GARMENT_ID_OFFLINE=1` default). Weights are stored as verified `safetensors` archives with SHA-256 checksums, uploaded images are stripped of metadata before prediction, and Cog serves HTTP `/predictions` on a non-root, read-only container with host-loopback SSRF URL rejection.

## Project Structure

- [backend/app/](backend/app/) — FastAPI gateway, image validation/stripping, preprocessing (`prepare_garment_tensor`), dual PyTorch architectures, HPO trainer, Cog HTTP client, and API schemas
- [run.py](run.py) — Cog `Runner` class exposing `/predictions` with dual-model output, startup SHA-256 verification, bounded base64/data-URI decoding, SSRF rejection, and structured `/tmp/garment-predictions.jsonl` event logging
- [frontend/](frontend/) — Static editorial UI (`index.html`, `app.js`, `ui.js`, `styles.css`) and local sample PNGs under `frontend/assets/`
- [scripts/](scripts/) — GPU/CPU HPO training (`train_models.py`), FashionMNIST sample asset generator (`generate_assets.py`), Postman payload helper (`prepare_postman.py`), preliminary PyTorch walkthrough (`preliminary_basics_demo.py`), Cog verifier (`verify_cog.py`), and Playwright browser E2E suite (`check_browser.py`)
- [tests/](tests/) — Automated `pytest` unit/integration suite (`95.00%` line/branch coverage reported against `fail_under = 85`)
- [docs/](docs/) — Detailed documentation:
  - [Model & HPO Benchmarks](docs/model.md)
  - [API Reference](docs/api.md)
  - [Architecture & Security](docs/architecture.md)
  - [Testing & Verification](docs/testing.md)
  - [Preliminary PyTorch Basics Notes](docs/preliminary-basics.md)
  - [Assignment Mapping](docs/assignment.md)
  - [Postman Collection](docs/postman/Atelier.postman_collection.json)

## Quick Start

### 1. Host Setup & Training

Requires Python `>=3.11,<3.13` and `uv`:

```bash
cd "Week 7/garment_id"
uv sync --frozen
```

Optional re-training (weights + benchmarks are already generated in `.cache/models/` and `backend/app/data/benchmark.json`):

```bash
uv run --frozen python scripts/train_models.py --device cuda
uv run --frozen python scripts/generate_assets.py
uv run --frozen python scripts/prepare_postman.py frontend/assets/shirt.png
```

Run the host FastAPI app directly without Cog:

```bash
./scripts/start.sh
```

Wait for readiness at `http://127.0.0.1:8000`.

### 2. Containerized Cog + Web Stack

Build the Cog inference image (`atelier-garment-id:cog`) and CPU web gateway (`atelier-garment-id:cpu`):

```bash
cd "Week 7/garment_id"
cog build --use-cog-base-image=false
docker compose -f compose.cog.yaml build web
docker compose -f compose.cog.yaml up -d --wait --wait-timeout 180
```

- Web UI & FastAPI proxy: `http://127.0.0.1:8000` (proxies `/api/identify` to Cog)
- Direct Cog `/predictions` endpoint: `http://127.0.0.1:5002/predictions`
- Inside-container prediction log stream:

```bash
docker compose -f compose.cog.yaml exec cog tail -f /tmp/garment-predictions.jsonl
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
uv run --frozen python scripts/prepare_postman.py frontend/assets/shirt.png
curl -sSf http://127.0.0.1:5002/predictions \
  -H 'Content-Type: application/json' \
  --data-binary @artifacts/postman/request.json
```

Postman GUI users can import [Atelier.postman_collection.json](docs/postman/Atelier.postman_collection.json) and send `POST http://127.0.0.1:5002/predictions`. See [docs/api.md](docs/api.md) for FastAPI and Cog payload schemas.

## Verification

Run lint, formatting, coverage-enforced tests, and JavaScript syntax checks:

```bash
cd "Week 7/garment_id"
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest --cov=backend/app --cov=run --cov-report=term-missing
node --check frontend/app.js && node --check frontend/ui.js
```

Run end-to-end Cog and Playwright browser checks against the live compose stack:

```bash
uv run --frozen python scripts/verify_cog.py
GARMENT_ID_ARTIFACT_DIR=artifacts/cog/browser uv run --frozen python scripts/check_browser.py
```

See [docs/testing.md](docs/testing.md) for full test inventory, container hardening verification, and recorded outputs.
