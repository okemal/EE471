# Testing & Verification — Atelier (`garment_id`)

All tests, lint checks, Cog container checks, and headless Chromium E2E checks documented here were executed against `Week 7/garment_id`.

## 1. Automated Python & JS Verification

### Test Suite & Coverage Threshold

`pyproject.toml` configures branch + line coverage over `backend/app` and `run.py` with `fail_under = 85`.

```bash
cd "Week 7/garment_id"
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest --cov=backend/app --cov=run --cov-report=term-missing
node --check frontend/app.js && node --check frontend/ui.js
```

| Check | Scope | Result |
|---|---|---|
| `pytest --cov` | `tests/test_*.py` (`test_api.py`, `test_architecture.py`, `test_catalogue.py`, `test_cog.py`, `test_decision.py`, `test_images.py`, `test_model.py`, `test_runner.py`, `test_training.py`) | `46 passed`, `95.00%` total coverage (`fail_under = 85`) |
| `ruff check .` | Python codebase + tests + scripts | `All checks passed!` |
| `ruff format --check .` | `37` Python files | Formatted cleanly |
| `node --check` | `frontend/app.js`, `frontend/ui.js` | Exit `0` |

### Key Test Modules

- [tests/test_architecture.py](../tests/test_architecture.py) — `QuickstartMLP`, `GarmentConvNet`, tensor shapes, parameter counts, and `prepare_garment_tensor` preprocessing (including auto-polarity inversion for light-background studio images vs dark FashionMNIST canvases)
- [tests/test_images.py](../tests/test_images.py) — MIME sniff/magic bytes, oversized stream rejection, corrupted payloads, EXIF/metadata stripping, dimension bounds
- [tests/test_decision.py](../tests/test_decision.py) — Side-by-side verdict agreement/disagreement synthesis and low-confidence thresholds
- [tests/test_model.py](../tests/test_model.py) — Dual model loading, SHA-256 `safetensors` checksum verification and tamper rejection, `predict()` formatting
- [tests/test_runner.py](../tests/test_runner.py) — Cog `Runner` setup, base64/data-URI prediction, SSRF URL rejection (`http://127.0.0.1`), and JSONL structured event writing
- [tests/test_cog.py](../tests/test_cog.py) & [tests/test_api.py](../tests/test_api.py) — FastAPI endpoints (`/api/health`, `/api/ready`, `/api/garments`, `/api/benchmarks`, `/api/identify`) and Cog HTTP client transport mocking
- [tests/test_training.py](../tests/test_training.py) — Synthetic FashionMNIST-like HPO training/evaluation loop and JSON report persistence

## 2. Container Build & Dependency Integrity

```bash
cd "Week 7/garment_id"
cog build --use-cog-base-image=false
docker compose -f compose.cog.yaml build web
docker run --rm --entrypoint python atelier-garment-id:cog -m pip check
```

- Cog image: `atelier-garment-id:cog`
- Web proxy image: `atelier-garment-id:cpu`
- `pip check` inside `atelier-garment-id:cog`: `No broken requirements found.`

## 3. Live Cog Inference, Security & Container Hardening

Both services start via `compose.cog.yaml` (`cog` on `127.0.0.1:5002`, `web` on `127.0.0.1:8000`) with `read_only` root filesystems, dropped capabilities (`cap_drop: [ALL]`), explicit thread limits (`OMP_NUM_THREADS=4`, `MKL_NUM_THREADS=4`, `OPENBLAS_NUM_THREADS=4`), and `pids_limit: 256` (updated from `128` after diagnosing `libgomp` OpenMP thread creation exhaustion on a 20-thread host).

```bash
cd "Week 7/garment_id"
docker compose -f compose.cog.yaml up -d --wait --wait-timeout 180
uv run --frozen python scripts/verify_cog.py
```

### Observed `verify_cog.py` Results (`http://127.0.0.1:5002`)

| Case | Baseline (`QuickstartMLP`) | Optimized (`GarmentConvNet`) | Evidence Artifact |
|---|---|---|---|
| `sneaker` | `Sneaker` (`0.495`) | `Sneaker` (`0.953`) | `artifacts/cog/verification.json` |
| `shirt` | `Pullover` (`0.257`) | `Shirt` (`0.992`) | `artifacts/cog/verification.json` |
| `ankle-boot` | `Ankle boot` (`0.377`) | `Ankle boot` (`0.963`) | `artifacts/cog/verification.json` |
| `studio-tee` | `Dress` (`0.315`) | `T-shirt/top` (`0.727`) | `artifacts/cog/verification.json` |
| `http://127.0.0.1/private` URL | Rejected (`failed` / non-HTTP error) | — | Logged as `{"event": "failed", ...}` |

### Container Non-Root Identity & Inside-Container JSONL Logs

```bash
docker compose -f compose.cog.yaml exec -T cog sh -c "id && tail -n 10 /tmp/garment-predictions.jsonl"
```

- Container user: `uid=10001 gid=10001 groups=10001` (non-root)
- Sample observed `/tmp/garment-predictions.jsonl` records:
  - `{"event": "prediction", ..., "status": "matched", "baseline_class": "Pullover", "baseline_confidence": 0.25687, "optimized_class": "Shirt", "optimized_confidence": 0.991991, "agreement": false, "elapsed_ms": 6}`
  - `{"event": "prediction", ..., "status": "matched", "baseline_class": "Ankle boot", "baseline_confidence": 0.377127, "optimized_class": "Ankle boot", "optimized_confidence": 0.963293, "agreement": true, "elapsed_ms": 8}`
  - `{"event": "failed", "request_id": "..."}` (SSRF private URL input rejected)

### Postman Payload CLI Check

```bash
uv run --frozen python scripts/prepare_postman.py frontend/assets/shirt.png
curl -sSf http://127.0.0.1:5002/predictions \
  -H 'Content-Type: application/json' \
  --data-binary @artifacts/postman/request.json
```

Observed output summary (`baseline`, `optimized`): `Pullover` / `Shirt`. (Interactive clicking inside the Postman Desktop GUI and screen-recording `Task-1-demo.avi` are manual user steps; see `Week 7/README.md`.)

## 4. Playwright Browser E2E Verification

```bash
GARMENT_ID_ARTIFACT_DIR=artifacts/cog/browser uv run --frozen python scripts/check_browser.py
```

Observed result: `Browser E2E checks passed with 0 page errors and 0 external requests.`

Verified checks:
- Home featured classes grid (`4` `.species-card` cards)
- File upload (`frontend/assets/shirt.png`), `#analysis-title` = `Shirt`, `6` probability bars across baseline & optimized cards, downloadable JSON result (`optimized.predicted_class == "Shirt"`)
- Sample pill (`sneaker`), invalid SVG upload error (`JPEG, PNG, or WebP`), oversized upload error (`too large`)
- Garment catalogue search (`boot` -> `1`), group filter (`Tops`), empty-search state, and reset (`10` cards)
- HPO & Benchmarks page: `4` KPI cards, `6` HPO trial rows, `10` per-class table rows, credits modal (`4` items)
- Responsive layout across `320px`, `390px`, `768px`, and `1024px` viewports with zero horizontal overflow (`scrollWidth <= innerWidth`), zero console/page errors, and zero outbound external HTTP requests
