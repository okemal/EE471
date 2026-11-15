# Testing & Verification — Vision10 (`cifar10_id`)

All tests, lint checks, Cog container checks, and headless Chromium E2E checks documented here were executed against `/home/onatkg/Programming/EE471/Week 7/cifar10_id`.

## 1. Automated Python & JS Verification

### Test Suite & Coverage Threshold

`pyproject.toml` configures branch + line coverage over `backend/app` and `run.py` with `fail_under = 85`.

```bash
cd "Week 7/cifar10_id"
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest --cov=backend/app --cov=run --cov-report=term-missing
node --check frontend/app.js && node --check frontend/ui.js
```

| Check | Scope | Result |
|---|---|---|
| `pytest --cov` | `tests/test_*.py` (`test_api.py`, `test_architecture.py`, `test_catalogue.py`, `test_cog.py`, `test_decision.py`, `test_images.py`, `test_model.py`, `test_runner.py`, `test_training.py`) | `45 passed`, `94.55%` total coverage (`fail_under = 85`) |
| `ruff check .` | Python codebase + tests + scripts | `All checks passed!` |
| `ruff format --check .` | `35` Python files | `35 files already formatted` |
| `node --check` | `frontend/app.js`, `frontend/ui.js` | Exit `0` |

### Key Test Modules

- [tests/test_architecture.py](../tests/test_architecture.py) — `TutorialCifarNet`, `CifarResNet9`, tensor shapes, parameter counts, and `prepare_cifar_tensor` preprocessing (native `32x32` pass-through vs. aspect-preserving center crop + bicubic resize)
- [tests/test_images.py](../tests/test_images.py) — Magic-byte validation, stream size cap rejection, corrupted image rejection, metadata stripping, dimension bounds
- [tests/test_decision.py](../tests/test_decision.py) — Baseline vs. optimized verdict synthesis and low-confidence fallback
- [tests/test_model.py](../tests/test_model.py) — `DualCifarClassifier` loading, SHA-256 `safetensors` digest enforcement, and top-k response formatting
- [tests/test_runner.py](../tests/test_runner.py) — Cog `Runner` setup, base64/data-URI prediction, SSRF private-network URL rejection, and JSONL structured logging
- [tests/test_cog.py](../tests/test_cog.py) & [tests/test_api.py](../tests/test_api.py) — FastAPI routes (`/api/health`, `/api/ready`, `/api/classes`, `/api/benchmarks`, `/api/identify`, `/api/identify-cog`) and Cog HTTP client transport mocking
- [tests/test_training.py](../tests/test_training.py) — Synthetic RGB dataset HPO runner (`apply_batch_augmentation`, `RandomCutout`, `evaluate_loader`) and benchmark JSON output

## 2. Container Build & Dependency Integrity

```bash
cd "Week 7/cifar10_id"
cog build --use-cog-base-image=false
docker compose -f compose.cog.yaml build web
docker run --rm --entrypoint python vision10-cifar-id:cog -m pip check
```

- Cog image: `vision10-cifar-id:cog`
- Web proxy image: `vision10-cifar-id:cpu`
- `pip check` inside `vision10-cifar-id:cog`: `No broken requirements found.`

## 3. Live Cog Inference, Security & Container Hardening

Both containers start via `compose.cog.yaml` (`cog` on `127.0.0.1:5003`, `web` on `127.0.0.1:8001`) with `read_only` root filesystems, dropped capabilities (`cap_drop: [ALL]`), bounded thread counts (`OMP_NUM_THREADS=4`, `MKL_NUM_THREADS=4`, `OPENBLAS_NUM_THREADS=4`), and `pids_limit: 256`.

```bash
cd "Week 7/cifar10_id"
docker compose -f compose.cog.yaml up -d --wait --wait-timeout 180
uv run --frozen python scripts/verify_cog.py
```

### Observed `verify_cog.py` Results (`http://127.0.0.1:5003`)

| Case | Baseline (`TutorialCifarNet`) | Optimized (`CifarResNet9`) | Evidence Artifact |
|---|---|---|---|
| `airplane` | `plane` (`0.379`) | `plane` (`0.878`) | [artifacts/cog/verification.json](../artifacts/cog/verification.json) |
| `cat` | `dog` (`0.317`) | `cat` (`0.604`) | [artifacts/cog/verification.json](../artifacts/cog/verification.json) |
| `ship` | `ship` (`0.809`) | `ship` (`0.867`) | [artifacts/cog/verification.json](../artifacts/cog/verification.json) |
| `automobile` | `car` (`0.469`) | `car` (`0.444`) | [artifacts/cog/verification.json](../artifacts/cog/verification.json) |
| `http://127.0.0.1/private` URL | Rejected (`failed` / SSRF block) | — | Logged as `{"event": "failed", ...}` |

### Container Non-Root Identity & Inside-Container JSONL Logs

```bash
docker compose -f compose.cog.yaml exec -T cog sh -c "id && tail -n 10 /tmp/cifar10-predictions.jsonl"
```

- Container user: `uid=10001 gid=10001 groups=10001` (non-root)
- Sample observed `/tmp/cifar10-predictions.jsonl` records:
  - `{"event": "ready", "device": "cpu", "baseline_test_accuracy": 0.558, "optimized_test_accuracy": 0.9249}`
  - `{"event": "prediction", ..., "status": "matched", "baseline_class": "plane", "baseline_confidence": 0.379153, "optimized_class": "plane", "optimized_confidence": 0.877858, "agreement": true, "elapsed_ms": 32}`
  - `{"event": "prediction", ..., "status": "matched", "baseline_class": "dog", "baseline_confidence": 0.317248, "optimized_class": "cat", "optimized_confidence": 0.603733, "agreement": false, "elapsed_ms": 7}`
  - `{"event": "prediction", ..., "status": "uncertain", "baseline_class": "car", "baseline_confidence": 0.468912, "optimized_class": "car", "optimized_confidence": 0.443838, "agreement": true, "elapsed_ms": 10}`
  - `{"event": "failed", "request_id": "..."}` (SSRF private URL input rejected)

### Postman Payload CLI Check

```bash
uv run --frozen python scripts/prepare_postman.py frontend/assets/cat.png
curl -sSf http://127.0.0.1:5003/predictions \
  -H 'Content-Type: application/json' \
  --data-binary @artifacts/postman/request.json
```

Observed output summary (`baseline`, `optimized`): `dog` / `cat`. (Clicking Send inside Postman Desktop GUI and recording `Task-2-demo.avi` are manual user steps; see `Week 7/README.md`.)

## 4. Playwright Browser E2E Verification

```bash
CIFAR10_ID_ARTIFACT_DIR=artifacts/cog/browser uv run --frozen python scripts/check_browser.py
```

Observed result: `Browser E2E checks passed with 0 page errors and 0 external requests.`

Verified checks:
- Featured CIFAR-10 classes grid (`4` cards)
- Upload (`frontend/assets/airplane.png`), `#analysis-title` = `Airplane`, `6` probability bars across baseline & optimized cards, downloadable JSON (`optimized.predicted_class == "plane"`)
- Sample pill (`cat`), invalid SVG upload error (`JPEG, PNG, or WebP`), oversize upload error (`too large`)
- CIFAR-10 classes guide search (`truck` -> `1`), group filter (`Animals`), empty-search state, and reset (`10` cards)
- HPO & Benchmarks page: `4` KPI cards, `5` HPO trial rows, `10` per-class table rows, credits modal (`2` items)
- Responsive layout across `320px`, `390px`, `768px`, and `1024px` viewports with zero horizontal overflow, zero page errors, and zero external requests
