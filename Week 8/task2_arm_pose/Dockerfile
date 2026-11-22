# Standalone Docker CLI image for Week 8 Task 2:
#   docker build -t ee471-week8-arm-pose:cli .
#   docker run --rm -v "$(pwd)/../input_photos:/inputs:ro" ee471-week8-arm-pose:cli /inputs/pose-1.jpg
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLBACKEND=Agg

RUN apt-get update && apt-get install -y --no-install-recommends \
        libegl1 \
        libgles2 \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libportaudio2 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app
COPY requirements-cog.txt ./
RUN pip install --no-cache-dir -r requirements-cog.txt

COPY arm_pose ./arm_pose
COPY classify_arm.py ./
COPY models/pose_landmarker_full.task ./models/pose_landmarker_full.task

USER 10001:10001
ENTRYPOINT ["python", "classify_arm.py"]
