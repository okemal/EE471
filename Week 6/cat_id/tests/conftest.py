"""Fast deterministic tests use a fake model; real inference is opt-in."""

import io
import threading
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.catalogue import species_catalogue
from backend.app.config import Settings
from backend.app.main import create_app


class FakeClassifier:
    status = "ready"
    device = "cpu"
    error = None

    def __init__(self):
        self.lock = threading.Lock()
        self.calls = 0
        self.fail = False

    def predict(self, image):
        self.calls += 1
        assert image.mode == "RGB"
        assert not image.info
        if self.fail:
            raise RuntimeError("test-only internal failure")
        return {
            "status": "matched",
            "message": "Closest visual match",
            "candidates": [{"species": species_catalogue()[0], "similarity": 0.5}],
            "diagnostics": {"cat_similarity": 0.3},
        }


@pytest.fixture
def config():
    return replace(Settings(), load_model=False, wikipedia_enabled=False)


@pytest.fixture
def engine():
    return FakeClassifier()


@pytest.fixture
def client(config, engine):
    with TestClient(create_app(config, engine), base_url="http://localhost") as client:
        yield client


@pytest.fixture
def jpeg():
    output = io.BytesIO()
    Image.new("RGB", (100, 80), "orange").save(output, "JPEG")
    return output.getvalue()
