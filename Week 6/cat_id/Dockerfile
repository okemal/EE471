# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.13.6 AS uv
FROM python:3.11-slim-bookworm AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
ARG INFERENCE_DEVICE=cpu
COPY pyproject.toml uv.lock requirements-cpu.lock ./
# CPU is deliberately the small, portable default. The CUDA variant uses uv.lock.
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$INFERENCE_DEVICE" = "cuda" ]; then \
      uv sync --frozen --no-dev; \
    else \
      uv venv --python /usr/local/bin/python /app/.venv && \
      uv pip sync --python /app/.venv/bin/python --require-hashes \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        --index-strategy unsafe-best-match requirements-cpu.lock; \
    fi

FROM python:3.11-slim-bookworm AS runtime
RUN useradd --create-home --uid 10001 felis
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --chown=felis:felis backend ./backend
COPY --chown=felis:felis frontend ./frontend
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CAT_ID_MODEL_CACHE=/models \
    CAT_ID_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1
USER felis
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=3)"
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--limit-concurrency", "8", "--no-access-log"]
