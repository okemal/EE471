FROM python:3.11-slim-bookworm AS runtime

# Azure's native SDK needs glibc, OpenSSL, ALSA and trusted HTTPS certificates.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libasound2 libssl3 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
WORKDIR /app
COPY speech-studio/requirements.lock /tmp/studio.lock
COPY common/requirements.lock /tmp/server.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/studio.lock -r /tmp/server.lock \
    && rm /tmp/studio.lock /tmp/server.lock

RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY speech-studio/*.py common/container_app.py common/healthcheck.py ./
COPY speech-studio/templates/ ./templates/
COPY speech-studio/static/ ./static/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 CMD ["python", "healthcheck.py"]
# One worker preserves the studio's process-local two-session limit. Threads
# allow WebSocket sessions, Azure requests and HTTP pages to coexist.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--worker-class", "gthread", "--threads", "8", "--timeout", "360", "--graceful-timeout", "10", "--worker-tmp-dir", "/tmp", "container_app:app"]

FROM runtime AS test
USER root
COPY common/requirements-test.lock /tmp/test.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/test.lock && rm /tmp/test.lock
COPY speech-studio/tests/ ./tests/
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
