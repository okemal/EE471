"""Cog 0.23.1 runner entrypoint serving face looking-direction classification."""

from __future__ import annotations

import json
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path as StdPath
from uuid import uuid4

from cog import BaseRunner, Input, Path

from face_direction.classifier import FaceDirectionClassifier
from face_direction.config import settings


class Runner(BaseRunner):
    """Cog runner exposing MediaPipe FaceLandmarker looking-direction classification."""

    def setup(self) -> None:
        """Verify and load face_landmarker.task once and configure JSONL prediction logs."""
        self.logger = logging.getLogger("week8.face_direction")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.logger.handlers.clear()
        self.logger.addHandler(logging.StreamHandler(sys.stdout))
        self.logger.addHandler(
            RotatingFileHandler(
                "/tmp/face-direction-predictions.jsonl", maxBytes=1_000_000, backupCount=1
            )
        )
        self.classifier = FaceDirectionClassifier(settings)
        self.classifier.load()
        self.logger.info(
            json.dumps(
                {
                    "event": "ready",
                    "model": settings.model_path.name,
                    "perspective": "viewer",
                }
            )
        )

    def run(
        self,
        image: Path = Input(  # noqa: B008
            description=(
                "Input portrait photo (JPEG, PNG, WebP, or BMP). "
                "Returns 'left', 'right', or 'straight'."
            )
        ),
    ) -> str:
        """Classify which direction the face is looking and return the exact label string."""
        request_id = uuid4().hex
        start = time.perf_counter()
        try:
            result, _, _ = self.classifier.predict_path(StdPath(image))
            elapsed_ms = round((time.perf_counter() - start) * 1000)
            self.logger.info(
                json.dumps(
                    {
                        "event": "prediction",
                        "request_id": request_id,
                        "direction": result.direction,
                        "signal_source": result.signal_source,
                        "yaw_deg": result.yaw_deg,
                        "asymmetry": result.asymmetry,
                        "elapsed_ms": elapsed_ms,
                    }
                )
            )
            return result.direction
        except Exception:
            self.logger.info(json.dumps({"event": "failed", "request_id": request_id}))
            raise
