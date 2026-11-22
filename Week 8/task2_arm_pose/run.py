"""Cog 0.23.1 runner entrypoint serving arm-up pose classification."""

from __future__ import annotations

import json
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path as StdPath
from uuid import uuid4

from cog import BaseRunner, Input, Path

from arm_pose.classifier import ArmPoseClassifier
from arm_pose.config import settings


class Runner(BaseRunner):
    """Cog runner exposing MediaPipe PoseLandmarker arm-up classification."""

    def setup(self) -> None:
        """Verify and load pose_landmarker_full.task once and configure JSONL prediction logs."""
        self.logger = logging.getLogger("week8.arm_pose")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.logger.handlers.clear()
        self.logger.addHandler(logging.StreamHandler(sys.stdout))
        self.logger.addHandler(
            RotatingFileHandler(
                "/tmp/arm-pose-predictions.jsonl", maxBytes=1_000_000, backupCount=1
            )
        )
        self.classifier = ArmPoseClassifier(settings)
        self.classifier.load()
        self.logger.info(
            json.dumps(
                {
                    "event": "ready",
                    "model": settings.model_path.name,
                    "perspective": "anatomical",
                }
            )
        )

    def run(
        self,
        image: Path = Input(  # noqa: B008
            description=(
                "Input photo (JPEG, PNG, WebP, or BMP) containing a person. "
                "Returns 'left', 'right', 'both', or 'None'."
            )
        ),
    ) -> str:
        """Classify which arm is raised in `image` and return the exact label string."""
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
                        "label": result.label,
                        "pose_detected": result.pose_detected,
                        "left_up": result.left.is_up if result.left else False,
                        "right_up": result.right.is_up if result.right else False,
                        "elapsed_ms": elapsed_ms,
                    }
                )
            )
            return result.label
        except Exception:
            self.logger.info(json.dumps({"event": "failed", "request_id": request_id}))
            raise
