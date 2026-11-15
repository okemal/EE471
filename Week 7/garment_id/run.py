"""Cog runner entry point; loads both FashionMNIST models once and serves POST /predictions."""

import json
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from uuid import uuid4

from cog import BaseRunner, Input

from backend.app.cog_transport import decode_data_uri
from backend.app.config import settings
from backend.app.model import DualGarmentClassifier
from backend.app.schemas import Identification


class Runner(BaseRunner):
    """Cog runner exposing side-by-side baseline and HPO-optimized garment inference."""

    def setup(self) -> None:
        """Load verified baseline and optimized checkpoints once and configure JSONL logging."""
        self.logger = logging.getLogger("atelier.predictions")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.logger.handlers.clear()
        self.logger.addHandler(logging.StreamHandler(sys.stdout))
        self.logger.addHandler(
            RotatingFileHandler("/tmp/garment-predictions.jsonl", maxBytes=1_000_000, backupCount=1)
        )
        self.classifier = DualGarmentClassifier(settings)
        self.classifier.load()
        if self.classifier.status != "ready":
            raise RuntimeError(self.classifier.error)
        self.logger.info(
            json.dumps(
                {
                    "event": "ready",
                    "device": self.classifier.device,
                    "baseline_test_accuracy": self.classifier.baseline_accuracy,
                    "optimized_test_accuracy": self.classifier.optimized_accuracy,
                }
            )
        )

    def run(
        self,
        image: str = Input(
            description=(
                "JPEG, PNG, or WebP garment image uploaded as a base64 data URI (10 MiB max)."
            )
        ),
    ) -> dict:
        """Decode the uploaded image and return side-by-side baseline and optimized predictions."""
        request_id = uuid4().hex
        start = time.perf_counter()
        decoded = None
        try:
            decoded = decode_data_uri(image, settings)
            result = self.classifier.predict(decoded)
            result.update(
                elapsed_ms=round((time.perf_counter() - start) * 1000),
                model=f"{DualGarmentClassifier.name} (Cog)",
                score_note=(
                    "Softmax probabilities come from independent FashionMNIST baseline and "
                    "HPO-optimized models trained on 28x28 grayscale studio garments."
                ),
            )
            validated = Identification.model_validate(result).model_dump(exclude_none=True)
            self.logger.info(
                json.dumps(
                    {
                        "event": "prediction",
                        "request_id": request_id,
                        "status": validated["status"],
                        "baseline_class": validated["baseline"]["predicted_class"],
                        "baseline_confidence": validated["baseline"]["confidence"],
                        "optimized_class": validated["optimized"]["predicted_class"],
                        "optimized_confidence": validated["optimized"]["confidence"],
                        "agreement": validated["comparison"]["agreement"],
                        "elapsed_ms": validated["elapsed_ms"],
                    }
                )
            )
            return validated
        except Exception:
            self.logger.info(json.dumps({"event": "failed", "request_id": request_id}))
            raise
        finally:
            if decoded is not None:
                decoded.close()
