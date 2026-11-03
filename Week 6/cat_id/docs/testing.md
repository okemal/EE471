# Verification record

Verified on 2–3 November 2026 in the local development environment. Tests describe
what was observed, not a guarantee of future model accuracy or deployment safety.
The original host/direct-container records are from 2 November; the Cog
assignment integration and updated automated suite were checked on 3 November.

## Automated application tests

`uv run --frozen pytest -q`: **66 passed** (49 original tests plus 17 Cog cases).

Coverage includes:

- JPEG, PNG, and WebP decoding; corrupt/truncated files; rejected SVG/GIF data;
  animated WebP rejection; minimum and maximum dimensions; encoded byte limits.
- EXIF orientation and metadata removal, transparent-pixel compositing, and
  reduction of large valid images before inference.
- Streaming-body enforcement even when the announced length is incorrect;
  single-request admission; safe model failures and lock release; explicit
  not-ready behaviour; no model execution for invalid uploads.
- Host and Origin restrictions, malformed origins, security headers, static-file
  boundaries, and typed species/identification responses.
- Matched, uncertain, and no-match decision paths, including non-finite scores.
- Catalogue uniqueness and counts for the declared taxonomy.
- Wikipedia attribution, caching, malformed or oversized replies, disambiguation,
  HTTP failures, and offline behaviour.
- Cog lossless image transport, invalid/oversized data URIs, rejection of remote
  image URLs and local-file paths, local service address restrictions, recovery
  after connection failure, malformed readiness replies, busy responses, and safe rejection of malformed
  model output without falling back to direct inference.

The test double is limited to model-independent tests. It is never selectable
by the application or exposed as a demo mode. There is one upstream Starlette
TestClient deprecation warning about its HTTPX integration; it does not cause a
test failure. A separate cancellation probe verified that cancelling an active
request retained the lock and image until the inference worker finished.

Both JavaScript modules passed `node --check`. CPU and GPU Compose definitions
passed `docker compose config --quiet`. Python sources were formatted with Ruff;
CSS was expanded into readable source rather than committed in minified form.

## Browser verification

`uv run --frozen python scripts/check_browser.py`: **passed** using isolated,
headless Chromium. The interactive browser connector was unavailable, so this
was an independently launched test browser, not control of the user's browser.

The script exercised real file upload and GPU inference for a domestic cat and
tiger, real rejection of the dog example, the real uncertain caracal case when
its evaluation photo was cached, result JSON download, species dialogs and
keyboard dismissal, search and filtering, empty-search feedback, unsupported
and oversized files, credits, and layout widths of 320, 390, 768, and 1024 px.
It also exercised an explicitly simulated uncertain response to cover the
rendering branch independently of weights. No browser page errors or external
browser requests were observed.

Desktop and mobile screenshots were inspected, including the upload page,
matched results, no-match state, and field guide. The test saves screenshots
under ignored `artifacts/`; these are QA evidence, not source dependencies.

## Real model smoke evaluation

`uv run --frozen python scripts/evaluate.py` examined **19 cases** on an NVIDIA
RTX 4050 Laptop GPU with 6 GB VRAM. The full recorded output and source links are
in [evaluation.json](evaluation.json).

Of ten cat photographs:

- Eight returned `matched` with the expected species: domestic cat, tiger,
  snow leopard, lion, leopard, cheetah, jaguar, and Eurasian lynx.
- A caracal returned `uncertain`. African golden cat ranked first at 0.6761;
  caracal ranked second at 0.6656. The 0.0105 margin is below the 0.015 species
  acceptance threshold. This is a real model confusion, not a confirmed match.
- Pallas's cat returned `uncertain` with the expected species first at 0.6177
  and Chinese mountain cat second at 0.6036 (margin 0.0141).

All nine tested negatives returned `no_match` with an empty candidate list:
dog, raccoon, red panda, horse, sunflower, white image, black image, seeded random
noise, and a synthetic text image. Wikimedia rate-limited acquisition of the fox
and hyena cases; they were not included in this record.

Observed GPU upload/decode/inference durations in this run ranged from 8 to
683 ms, with the first inference slower. The result does not include optional
Wikipedia latency. These are single requests on one laptop, not a throughput
benchmark. A CPU-only invocation also loaded both models and identified the
domestic-cat example correctly: about 37 seconds to initialize, 2.8 seconds for
that prediction, and approximately 8,860 MiB peak process RSS. CPU timing was
measured while the local GPU web service also existed and is illustrative.

These public photos are a small convenience sample and may overlap model
training data. There is no independent species-balanced test set, confidence
calibration, robustness certification, or measured general false-accept rate.
Thresholds were not tuned on these outcomes. Do not convert this smoke check
into an advertised accuracy percentage.

## Knowledge and offline operation

A direct live Wikipedia summary lookup for the domestic cat succeeded and
returned a cited CC BY-SA 4.0 overview. The development network returned a `403`
for one Action API request shape; the application uses the tested page-summary
endpoint instead. Tests verify that blocked, failed, malformed, oversized, and
missing responses fall back to the local profile.

The browser/model checks ran with `CAT_ID_OFFLINE=1` using previously cached,
revision-pinned weights. Curated species profiles, fonts, and example photos
were available without external browser requests. Actual outbound network
firewall isolation was not separately enforced during that run.

## Container verification

The following is the original **direct-inference** container record. The current
assignment's two-container Cog stack is verified separately below.

The **CPU container is now verified end to end** with Docker Desktop 4.97.0,
Docker Engine 29.9.2, and Docker Compose 5.6.1 on the `desktop-linux` context.
The earlier daemon interruption no longer blocks this path.

- `docker compose build` completed successfully using the hashed CPU dependency
  lock. The running image is
  `sha256:e58b253a1d437801455c59a80202a5e4d4c792502849336ba7525d72ecb84457`.
- `docker compose up -d --no-build` reached Docker health status `healthy` and
  `/api/ready` returned `200`. The API reports `device: cpu`, `offline: true`,
  and the expected BioCLIP model and 41-entry catalogue.
- All 19 functional smoke cases completed inside the container. Eight cats
  matched the expected species, two remained uncertain, and all nine negatives
  were rejected. The complete CPU output is in
  [container-evaluation.json](container-evaluation.json). Cat-ranking requests
  took about 3.0–4.0 seconds; negative examples took 105–164 ms in this run.
- The full browser script passed against the container: real uploads,
  identification, no-match handling, actual and simulated uncertainty, JSON
  download, search/filtering, validation, dialogs, and responsive layouts.
  Screenshots are under ignored `artifacts/container/browser/`.
- All **28 packaged backend/frontend files** were compared by SHA-256 with this
  checkout and matched byte for byte. After the later interruption, the same
  image was restarted, readiness was rechecked, and the browser workflow passed.
- Runtime inspection confirmed UID 10001, a read-only root filesystem and model
  mount, all capabilities dropped, `no-new-privileges`, and port 8000 published
  only on `127.0.0.1`. No OOM kills were recorded.

Docker Desktop initially exposed only 3.6 GiB of RAM. With the user's approval,
its `MemoryMiB` setting was raised to **10240 (10 GiB)** and Desktop was restarted.
The engine reports about 9.7 GiB after VM overhead. The measured peak container
memory was approximately 8.8 GiB. Both pre-existing speech-demo containers were
restored and verified healthy after the restart. A timestamped backup of the
original Desktop settings was retained beside `settings-store.json`.

The Compose `mem_limit` is a container ceiling, not an allocation of additional
memory to Docker Desktop. A fresh Desktop installation needs its VM memory
increased before this model can run. Leave headroom for other workloads.

A separate `--gpus all` probe was rejected by this Docker engine with
`failed to discover GPU vendor from CDI: no known GPU vendor found`. The CUDA
container therefore remains unverified; this successful container run used CPU
inference. Docker's [GPU passthrough documentation](https://docs.docker.com/desktop/features/gpu/)
covers its Windows/WSL 2 backend. Host GPU inference remains a separately verified
local launch path.

To reproduce while the Compose service is running:

```bash
CAT_ID_ARTIFACT_DIR=artifacts/container uv run --frozen python scripts/evaluate.py
CAT_ID_ARTIFACT_DIR=artifacts/container/browser uv run --frozen python scripts/check_browser.py
```

## Cog assignment verification (3 November)

`cog build --use-cog-base-image=false` and the web Docker build completed with
Cog CLI/SDK/coglet 0.23.1. The plain Python base avoids an unused OpenCV/NumPy
dependency conflict in Cog's prebuilt base. `python -m pip check` inside the
final Cog container returned **No broken requirements found**. Cog consumes
pinned versions from the shared CPU lock through its generated install steps;
the hand-written web Dockerfile additionally enforces the lock's hashes.

`docker compose -f compose.cog.yaml up -d --wait --wait-timeout 240` started both
services with healthy status. The website at port 8000 uses the Cog service at
port 5002; web loads no vision models. Both run as UID 10001 with read-only roots,
dropped capabilities, no-new-privileges, and loopback-only ports. No OOM kills
were recorded. All 31 packaged backend/frontend files in web, and those files
plus `run.py`, `cog.yaml`, and the CPU lock in Cog, matched the checkout by SHA-256.
Both existing speech containers remained healthy on ports 5000 and 5001.

`scripts/verify_cog.py` exercised real `POST /predictions` requests and verified:

- Domestic cat: species `Felis catus`, tutorial ResNet50 class `tabby`.
- Tiger: species `Panthera tigris`, tutorial ResNet50 class `tiger`.
- Dog: `no_match` with no species candidates, ResNet50 class `golden retriever`.
- A submitted HTTP image URL was rejected without remote image fetching.

The full browser script passed against this final stack, including the new
baseline panel, the exported baseline fields, real cat/tiger/dog/caracal cases,
keyboard/dialogs, filters, upload validation, and four responsive widths.
Desktop and mobile result screenshots were inspected. The 19-image smoke set
also completed through the website and Cog: **eight correct matched cats, two
uncertain cats, and nine rejected negatives**, consistent with the earlier
species results. Observed web-request durations were 105–2406 ms in this run.
These convenience cases remain unsuitable as a general accuracy estimate.

Inside-container `exec`, `id`, and reads of `/tmp/felis-predictions.jsonl`
confirmed the live prediction records contain status, ImageNet class, closest
species, and duration. Photos and filenames are absent. The log is a rotating
tmpfs file; the application also writes these events to container stdout.

The Postman collection and generated environment form a real uploaded-image
request; that exact resolved payload was also sent to Cog successfully using
HTTPX. **The Postman desktop UI and the required AVI recordings have not been
recorded or verified here.** The student must demonstrate Postman in Task 2 and
provide the narrated code explanation. Follow [assignment.md](assignment.md).

Reproducible commands and local evidence:

```bash
uv run --frozen python scripts/verify_cog.py
CAT_ID_ARTIFACT_DIR=artifacts/cog/browser uv run --frozen python scripts/check_browser.py
CAT_ID_ARTIFACT_DIR=artifacts/cog uv run --frozen python scripts/evaluate.py
```

Generated API records, screenshots, Postman upload data, build logs, and runtime
checks are under ignored `artifacts/`. They contain no additional source files
needed to run the application. Model caches, `.cog/` build intermediates, and
AVI recordings are also excluded from version control.
