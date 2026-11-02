#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export HF_HUB_DISABLE_TELEMETRY=1
exec uv run --frozen uvicorn backend.app.main:app \
  --host 127.0.0.1 --port "${CAT_ID_PORT:-8000}" --workers 1 \
  --limit-concurrency 8 --timeout-keep-alive 5 --no-access-log
