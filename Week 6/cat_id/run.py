"""Cog's model entry point; loaded once, then called by POST /predictions."""

import json
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from uuid import uuid4

from cog import BaseRunner, Input

from backend.app.cog_transport import decode_data_uri
from backend.app.config import settings
from backend.app.model import BIOCLIP, Classifier
from backend.app.resnet import ResNetBaseline
from backend.app.schemas import Identification


class Runner(BaseRunner):
    def setup(self):
        """Keep one copy of each model and a bounded prediction log in RAM-backed /tmp."""
        self.logger = logging.getLogger("felis.predictions")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.logger.handlers.clear()
        self.logger.addHandler(logging.StreamHandler(sys.stdout))
        self.logger.addHandler(
            RotatingFileHandler("/tmp/felis-predictions.jsonl", maxBytes=1_000_000, backupCount=1)
        )
        self.classifier = Classifier(settings)
        self.classifier.load()
        if self.classifier.status != "ready":
            raise RuntimeError(self.classifier.error)
        self.baseline = ResNetBaseline(settings, self.classifier.device)
        self.logger.info(json.dumps({"event": "ready", "device": self.classifier.device}))

    def run(
        self,
        image: str = Input(
            description="JPEG, PNG, or WebP uploaded as a base64 data URI (10 MiB maximum)."
        ),
    ) -> dict:
        """Classify with the tutorial ResNet50 and the broader Felidae species model.

        A string input deliberately avoids Cog Path's remote fetching and disk
        spooling. Both the browser and Postman send the actual image bytes.
        """
        request_id = uuid4().hex
        start = time.perf_counter()
        decoded = None
        try:
            decoded = decode_data_uri(image, settings)
            baseline = self.baseline.predict(decoded)
            result = self.classifier.predict(decoded)
            result.update(
                baseline=baseline,
                elapsed_ms=round((time.perf_counter() - start) * 1000),
                model=f"{BIOCLIP.name} + ResNet50 (Cog)",
                score_note="Cosine similarities are not probabilities or verified confidence.",
            )
            result = Identification.model_validate(result).model_dump(exclude_none=True)
            self.logger.info(
                json.dumps(
                    {
                        "event": "prediction",
                        "request_id": request_id,
                        "status": result["status"],
                        "predicted_class": baseline["predicted_class"],
                        "closest_species": result["candidates"][0]["species"]["scientific_name"]
                        if result["candidates"]
                        else None,
                        "elapsed_ms": result["elapsed_ms"],
                    }
                )
            )
            return result
        except Exception:
            self.logger.info(json.dumps({"event": "failed", "request_id": request_id}))
            raise
        finally:
            if decoded is not None:
                decoded.close()
