# Vision10 System Architecture

Vision10 pairs two local PyTorch models inside a Cog model container behind a FastAPI web service and static ES-module browser frontend.

## Runtime Components

| Component | Role | Security & Isolation |
|---|---|---|
| Browser SPA (`frontend/`) | Drag/drop upload UI, side-by-side cards, HPO tables, 10-class catalogue | Strict CSP (`default-src 'self'`), self-hosted fonts, text-only DOM builder (`ui.js`) |
| FastAPI Server (`backend/app/main.py`) | Upload validation, EXIF stripping, `/api/classes`, `/api/benchmarks`, `/api/identify` | `TrustedHostMiddleware`, same-origin POST enforcement, single-flight lock, `10 MiB` bound |
| Cog Runner (`run.py`, `cog.yaml`) | Loads `baseline.safetensors` & `optimized.safetensors`, serves `POST /predictions` | Non-root user (`10001`), read-only filesystem, `cap_drop: ALL`, JSONL logs in `/tmp/cifar10-predictions.jsonl` |

## Data & Inference Flow

1. User uploads a JPEG, PNG, or WebP image (minimum `32×32`, max `10 MiB`, max `20 MP`).
2. `backend/app/images.py` verifies format, pixel bounds, and single-frame constraint (`n_frames == 1`), applies EXIF transpose, composites transparency onto white, caps large images to `1600×1600`, and copies raw RGB bytes to strip metadata.
3. In Cog compose mode (`compose.cog.yaml`), `CogClassifier` encodes the sanitized image as a bounded PNG data URI (`data:image/png;base64,...`) and posts it to `http://cog:5000/predictions`.
4. Inside Cog (`run.py`), `decode_data_uri()` rejects remote HTTP/file URLs and decodes pixels; `DualCifarClassifier` verifies SHA-256 checksums, constructs a normalized `(1, 3, 32, 32)` tensor (with center square crop when aspect ratio > `1.25`), and runs both `TutorialCifarNet` and `CifarResNet9`.
5. FastAPI returns the validated `Identification` payload with side-by-side confidences, top-3 class probabilities, accuracy delta, agreement status, and timing metrics.
