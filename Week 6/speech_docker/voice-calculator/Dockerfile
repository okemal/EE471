FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
WORKDIR /app
COPY voice-calculator/requirements.lock /tmp/calculator.lock
COPY common/requirements.lock /tmp/server.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/calculator.lock -r /tmp/server.lock \
    && rm /tmp/calculator.lock /tmp/server.lock
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY voice-calculator/*.py common/container_app.py common/healthcheck.py ./
COPY voice-calculator/templates/ ./templates/
COPY voice-calculator/static/ ./static/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 CMD ["python", "healthcheck.py"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--worker-class", "gthread", "--threads", "4", "--timeout", "60", "--graceful-timeout", "10", "--worker-tmp-dir", "/tmp", "container_app:app"]

FROM runtime AS test
COPY voice-calculator/tests/ ./tests/
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
