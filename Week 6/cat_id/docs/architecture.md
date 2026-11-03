# Architecture and operational boundaries

## Components

A single FastAPI process serves the static HTML/CSS/ES-module frontend and JSON
API. The frontend has no build system or runtime CDN dependencies. This keeps a
local demonstration easy to launch and gives the browser a single origin.

In direct mode the server owns one `Classifier`, two pretrained vision-language models, their
precomputed text embeddings, a validated species catalogue, and a small optional
Wikipedia cache. Model loading runs in a worker thread so the site and health
endpoint remain available during initialization. Inference and image decoding
also run outside the event loop.

In the assignment's `compose.cog.yaml` stack, `CogClassifier` delegates to
`http://cog:5000/predictions` on the Compose network. The web container loads no
weights. Cog's `Runner.setup()` loads the two species-model checkpoints and the
tutorial's ResNet50 `IMAGENET1K_V1` once. `Runner.run()` returns both the original
species decision and a separate ResNet50 ImageNet classification. The UI shows
both; no ImageNet class is silently converted into a species name. Cog itself
admits one synchronous prediction; direct API contention returns `409`, mapped
to `429` by the website. There is no fallback that bypasses Cog on failure.

The catalogue, model prompts, and decision rules are independent modules. The
HTTP layer handles status codes, limits, concurrency, and response validation.
The UI renders dynamic strings using DOM `textContent`, never HTML from API
responses. Public response shapes are defined in `schemas.py` and exposed in
the OpenAPI document.

## Request lifecycle

1. The browser checks basic file type, byte size, and displayed dimensions, then
   previews the selected file with a temporary object URL. Object URLs are
   revoked when the photo is replaced, cleared, or the page is closed.
2. On an explicit **Identify** click, it posts the image bytes to `/api/identify`.
   The filename is not included. There is no multipart parser or file spool.
3. The server checks content type, announced size, model readiness, and its
   single-request admission lock. A second image request receives `429`.
4. It reads bounded chunks with a 30-second upload deadline, independently of
   `Content-Length`. Pillow checks the actual format, frame count, dimensions,
   integrity, and decompression warnings before model inference.
5. EXIF orientation is applied. Transparency is composited on white, the image
   is reduced to a maximum 1600-pixel side, and a new pixel-only RGB image is
   created. Source metadata does not pass to the classifier.
6. OpenCLIP checks cat evidence. Only accepted images proceed to BioCLIP species
   ranking and the separate uncertainty decision.
   In Cog mode the validated pixels travel as a lossless PNG data URI; Cog
   validates them again and also runs the required ResNet50 baseline.
7. The image is closed and the admission lock released. A matched result may
   receive optional Wikipedia enrichment, with a sourced local fallback.
8. The response includes the outcome, up to three species candidates, raw cosine
   similarities, decision diagnostics, and inference duration. It contains no
   photograph, filename, EXIF, or location.

The duration excludes optional knowledge retrieval. Browser cancellation drops
stale responses, but an already running GPU operation may finish on the server.
The worker remains protected while it finishes. A subsequent request can receive
`429`; cancellation is not a claim that an executing CUDA kernel was stopped.

## Resource and input limits

- 10 MiB maximum encoded image, checked before and during body consumption.
- 20 million decoded pixels; at most 12,000 pixels on either dimension.
- At least 32 pixels on both sides; only still JPEG, PNG, and WebP.
- One decode/inference request at a time; eight HTTP connections/tasks at the
  provided Uvicorn launch limit. These are local resource controls, not an
  internet-facing rate-limiting service.
- Wikipedia: fixed host and catalogue titles, no redirects, five-second overall
  fetch deadline, 100 KB decoded-response limit, and one upstream request at a
  time. Successful entries expire after 24 hours; failed entries after a minute.
- One process/worker. GPU uses mixed fp16 model precision; CPU uses fp32.

## Privacy and security

The supported launch binds to `127.0.0.1`. Docker publishes the port only on host
loopback. Host validation and Origin/Fetch Metadata checks reject unrelated
browser origins. There is no CORS wildcard, arbitrary URL-import feature, login,
analytics, database, upload directory, or image history.

The static file mount exposes only `frontend/`. Browser headers restrict scripts,
styles, fonts, and fetches to the local origin, disallow object embedding and
framing, prevent MIME sniffing, and disable camera, microphone, and geolocation
permissions. API responses use `Cache-Control: no-store`.

The BioCLIP/OpenCLIP downloader uses exact repository revisions and safetensors files.
No user-provided model or remote Python code is loaded. The server logs model and
operational errors, not request bodies or filenames. The launcher disables
access logs. Optional Wikipedia queries disclose a species article title to
Wikipedia; disabling them or enabling offline mode removes that traffic.

ResNet50 uses the official TorchVision checkpoint, verifies its full SHA-256,
and loads only a state dictionary with `weights_only=True`. The Cog predictor
accepts an image string containing a data URI, not `cog.Path`, so it does not
download arbitrary URLs or spool photos to disk. The same decoder bounds actual
image bytes/pixels; Cog parses the JSON envelope before that application check.
The separately exposed Cog API is a trusted local tooling endpoint, bound only
to host loopback, and does not inherit the website's browser-origin middleware.
Use Postman/curl locally; it is not a public upload service. Cog's own protocol
may echo `input` in its response; the web proxy exposes only validated output.
Postman's generated environment and request files contain image pixels and are
stored only under ignored `artifacts/` when explicitly prepared for the demo.

`/tmp/felis-predictions.jsonl` records per-request events with a random ID,
result, top ImageNet class, closest species (including uncertain outcomes), and
duration. It rotates at 1 MB with one backup and contains no photo, filename,
or EXIF. This file lives in container tmpfs and can be followed with
`docker compose -f compose.cog.yaml exec cog tail -F /tmp/felis-predictions.jsonl`.
The same events go to Docker's standard logs. `/tmp` contents disappear when
the container is removed/recreated; Docker log retention is managed separately.

Memory-only processing does not mean cryptographic erasure from RAM, OS swap,
browser internals, or system crash dumps. The original image stays wherever the
user stored it. **Save observation** is an explicit client-side download of the
result JSON and excludes the image.

This configuration is for a trusted local educational demo. Public deployment
would require its own threat model, authentication, TLS, distributed admission
control, operational monitoring, abuse controls, and a stronger evaluated
open-set decision policy. Those concerns are outside this application's local
scope.

## Failure behavior

Loading/disabled/error states are visible through `/api/health`; `/api/ready`
returns `503` until inference is ready. Initialization errors do not silently
switch model versions or manufacture outputs. If CUDA is explicitly required
but unavailable, the app reports an error rather than pretending to use it.

Invalid images receive concise validation messages. Unexpected inference errors
return a generic `503`; stack traces remain in the local server log. An upstream
Wikipedia failure cannot turn an otherwise valid identification into an error.
The UI includes retry, replace-photo, and start-over paths. Request IDs and abort
controllers prevent a late response from overwriting a newer photo selection.
