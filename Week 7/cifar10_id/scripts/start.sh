#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
exec uv run --frozen uvicorn backend.app.main:app \
  --host 127.0.0.1 --port "${CIFAR10_ID_PORT:-8001}" --workers 1 \
  --limit-concurrency 8 --timeout-keep-alive 5 --no-access-log
