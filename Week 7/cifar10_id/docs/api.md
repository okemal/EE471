# Vision10 HTTP API Reference

FastAPI serves both the web frontend and local JSON endpoints on `http://127.0.0.1:8001` (host) or via `compose.cog.yaml` (`web:8000` -> host `8001`, `cog:5000` -> host `5003`). Interactive Swagger docs are disabled (`docs_url=None`, `redoc_url=None`); OpenAPI metadata is served at `GET /api/openapi.json`.

## Web Server Endpoints

### `GET /api/health`
Returns readiness, active device (`cpu` or `cuda`), model name, class count (`10`), offline flag, byte limit (`10485760`), and measured baseline/optimized test accuracies.

### `GET /api/ready`
Returns `200 {"status": "ready"}` when both models (or the upstream Cog service) are ready; otherwise returns `503`.

### `GET /api/classes` and `GET /api/classes/{class_id}`
Returns all 10 CIFAR-10 categories (`airplane`, `automobile`, `bird`, `cat`, `deer`, `dog`, `frog`, `horse`, `ship`, `truck`) enriched with per-class baseline and HPO test accuracies. Unknown `class_id` values return `404`.

### `GET /api/benchmarks`
Returns `BenchmarkReport` from `backend/app/data/benchmark.json` containing `baseline`, `optimized`, `trials`, `per_class_accuracy`, and `epoch_history`. Returns `404` if benchmark metrics have not been generated yet.

### `POST /api/identify`
Accepts raw binary `image/jpeg`, `image/png`, `image/webp`, or `application/octet-stream` payloads (`<= 10 MiB`, `>= 32x32` px) with same-origin enforcement and single-request admission control (`429 Retry-After: 3` while busy).

Status codes:
- `200`: Valid `Identification` JSON (`status`, `message`, `candidates`, `baseline`, `optimized`, `comparison`, `diagnostics`, `elapsed_ms`, `model`, `score_note`)
- `400`: Malformed `Content-Length`
- `408`: Upload body timed out (`30s`)
- `413`: Exceeds `10 MiB`
- `415`: Unsupported `Content-Type`
- `422`: Corrupt, non-image, animated, too small (`< 32px`), or too large (`> 20 MP` / `> 12000px`)
- `429`: Concurrent inference request rejected
- `503`: Classifier not ready or upstream failure

## Cog Prediction Server Endpoints (`http://127.0.0.1:5003`)

- `GET /health-check`: Reports Cog runner state (`READY`, `BUSY`, `STARTING`, `SETUP_FAILED`).
- `POST /predictions`: Accepts `{"input": {"image": "data:image/png;base64,..."}}`. Rejects non-data-URI URLs (returns `"status": "failed"`) and logs anonymous JSON events to `stdout` and `/tmp/cifar10-predictions.jsonl`.
