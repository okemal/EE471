# Architecture · Atelier FashionMNIST Garment Classifier

## System Overview

Atelier separates untrusted user upload handling in the FastAPI web tier from PyTorch model execution in the Cog inference service:

```text
Browser (frontend/) ──POST /api/identify──▶ FastAPI (backend/app/main.py)
                                                 │
                                    Validate bytes, strip EXIF,
                                    encode lossless PNG data URI
                                                 │
                                                 ▼
                                     Cog HTTP Service (run.py:Runner)
                                      ├─ QuickstartMLP (baseline.safetensors)
                                      └─ GarmentConvNet (optimized.safetensors)
```

## Security & Robustness Boundaries

1. **Upload Validation (`backend/app/images.py`)**: Enforces 10 MB byte limit while streaming (ignoring untrusted `Content-Length`), verifies magic headers (`JPEG`, `PNG`, `WEBP`), blocks animated frames and decompression bombs (>20 MP or >12,000 px), requires >=28 px per side, composites alpha over white, and copies raw RGB pixels via `Image.frombytes` to strip all EXIF/GPS/filename metadata.
2. **Same-Origin & Security Headers (`backend/app/main.py`)**: `TrustedHostMiddleware` restricts host headers to loopback (`localhost`, `127.0.0.1`, `[::1]`). `POST` requests enforce same-origin checks and reject `sec-fetch-site: cross-site`. Responses set strict `CSP` (`default-src 'self'`), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and `Cache-Control: no-store` on API endpoints.
3. **Cog Transport (`backend/app/cog_transport.py`, `backend/app/cog_client.py`)**: Uses base64 data URIs rather than remote image URLs so Cog never fetches attacker-supplied URLs (`http://`, `https://`, `file://` are explicitly rejected).
4. **Admission Control**: Single-flight `threading.Lock()` prevents concurrent GPU/CPU memory spikes and returns HTTP `429` with `Retry-After: 3` when busy.
5. **Artifact Integrity (`backend/app/model.py`)**: Weights are stored in `safetensors` (no `pickle` deserialization) and verified against SHA-256 hashes recorded in `.cache/models/manifest.json`.
6. **Container Hardening (`compose.cog.yaml`, `Dockerfile`)**: Both `cog` and `web` run as non-root UID `10001` with `read_only: true`, RAM-backed `/tmp` tmpfs, `cap_drop: [ALL]`, `no-new-privileges:true`, and loopback-only host bindings.
