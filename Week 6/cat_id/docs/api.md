# Local HTTP API

Base URL: `http://127.0.0.1:8000`. Machine-readable contracts are available at
`GET /api/openapi.json`. The application does not load a third-party Swagger UI.

## Identify

`POST /api/identify` accepts **raw image bytes**, not multipart form data or a
remote URL. Supported request content types are `image/jpeg`, `image/png`,
`image/webp`, and `application/octet-stream`. The decoded format is independently
verified. A MIME type or extension is never treated as proof of file content.

```bash
curl --fail-with-body http://127.0.0.1:8000/api/identify \
  -H 'Content-Type: image/jpeg' \
  --data-binary @frontend/assets/domestic-cat.jpg
```

A successful HTTP `200` can have three application outcomes:

- `matched`: a closest visual match; `candidates` has up to three entries and
  `knowledge` contains a cited live or local overview for the first candidate.
- `uncertain`: sufficient cat evidence, insufficient species separation;
  candidates are suggestions to compare, not confirmed identities.
- `no_match`: insufficient cat evidence; the candidate list is empty.

Each candidate includes a `species` profile and `similarity` (cosine similarity
in `[-1, 1]`, not a confidence percentage). Responses also include `message`,
`model`, `score_note`, `elapsed_ms`, and `diagnostics` with cat similarity and
applicable margins. `elapsed_ms` measures upload/decode/inference and excludes
optional Wikipedia retrieval.

Operational errors are distinct from no-match outcomes:

- `400`: malformed upload length or untrusted Host.
- `403`: unrelated browser Origin or cross-site upload.
- `408`: upload exceeded the 30-second streaming deadline.
- `413`: encoded image exceeded 10 MiB.
- `415`: unsupported request Content-Type.
- `422`: unsupported decoded format, corrupt image, animation, or invalid dimensions.
- `429`: another image is in progress; inspect `Retry-After`.
- `503`: model is loading, disabled, failed, or could not complete inference.

Application errors use `{"detail": "human-readable message"}`. Uvicorn may
return a plain `503` when its own HTTP concurrency limit is reached. There is no
queue, batch endpoint, arbitrary URL fetch, or public API authentication layer.

## Health and readiness

`GET /api/health` is available while models load. Its `status` is `loading`,
`ready`, `error`, or `disabled`. It also reports device, model name, catalogue
count, offline mode, maximum upload bytes, and any safe initialization error.

`GET /api/ready` returns `200` only after inference is ready; otherwise `503`.
It is suitable for the container health check. Liveness and model readiness are
intentionally separate.

## Catalogue

`GET /api/species` returns the 41 species profiles and the taxonomy reference.

`GET /api/species/{species_id}` returns one known profile and optional knowledge
summary. Unknown IDs return `404`; they are not forwarded to Wikipedia. For
example: `/api/species/domestic-cat`.

Species records contain `id`, `common_name`, `scientific_name`, `genus`,
`subfamily`, `wikipedia_title`, `summary`, `range`, `habitat`, `identification`,
`source_url`, `taxonomy_note`, and `aliases`.

Knowledge records identify their source, source URL, live/fallback state,
licence when applicable, and retrieval timestamp. Preserve the catalogue's name
and `taxonomy_note` even when showing a newer Wikipedia article.
