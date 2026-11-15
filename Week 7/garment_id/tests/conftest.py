"""Shared pytest fixtures and deterministic test double for garment API tests."""

import io
import json
import threading
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.catalogue import garment_catalogue
from backend.app.config import Settings
from backend.app.main import create_app


class FakeGarmentClassifier:
    """Model-independent test double matching the DualGarmentClassifier contract."""

    name = "QuickstartMLP + GarmentConvNet (Test)"
    status = "ready"
    device = "cpu"
    error = None
    baseline_accuracy = 0.65
    optimized_accuracy = 0.93

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls = 0
        self.fail = False

    def predict(self, image: Image.Image) -> dict:
        self.calls += 1
        assert image.mode == "RGB"
        assert not image.info
        if self.fail:
            raise RuntimeError("test-only internal failure")
        catalogue = garment_catalogue()
        return {
            "status": "matched",
            "message": "Confident garment category match from the optimized CNN.",
            "candidates": [
                {
                    "garment": catalogue[7],
                    "probability": 0.92,
                    "baseline_probability": 0.61,
                },
                {
                    "garment": catalogue[9],
                    "probability": 0.05,
                    "baseline_probability": 0.22,
                },
                {
                    "garment": catalogue[5],
                    "probability": 0.02,
                    "baseline_probability": 0.10,
                },
            ],
            "baseline": {
                "model_id": "baseline",
                "model_name": "PyTorch Quickstart Baseline MLP",
                "architecture": "QuickstartMLP",
                "hyperparameters": {
                    "optimizer": "SGD",
                    "learning_rate": 0.001,
                    "batch_size": 64,
                    "epochs": 5,
                },
                "test_accuracy": 0.65,
                "predicted_class": "Sneaker",
                "predicted_display_name": "Sneaker",
                "predicted_id": "sneaker",
                "confidence": 0.61,
                "top_classes": [
                    {
                        "label": "Sneaker",
                        "display_name": "Sneaker",
                        "class_id": "sneaker",
                        "probability": 0.61,
                    },
                    {
                        "label": "Ankle boot",
                        "display_name": "Ankle boot",
                        "class_id": "ankle-boot",
                        "probability": 0.22,
                    },
                    {
                        "label": "Sandal",
                        "display_name": "Sandal",
                        "class_id": "sandal",
                        "probability": 0.10,
                    },
                ],
                "elapsed_ms": 1.2,
            },
            "optimized": {
                "model_id": "optimized",
                "model_name": "HPO-Optimized GarmentConvNet",
                "architecture": "GarmentConvNet",
                "hyperparameters": {
                    "optimizer": "AdamW",
                    "learning_rate": 0.001,
                    "batch_size": 64,
                    "epochs": 20,
                },
                "test_accuracy": 0.93,
                "predicted_class": "Sneaker",
                "predicted_display_name": "Sneaker",
                "predicted_id": "sneaker",
                "confidence": 0.92,
                "top_classes": [
                    {
                        "label": "Sneaker",
                        "display_name": "Sneaker",
                        "class_id": "sneaker",
                        "probability": 0.92,
                    },
                    {
                        "label": "Ankle boot",
                        "display_name": "Ankle boot",
                        "class_id": "ankle-boot",
                        "probability": 0.05,
                    },
                    {
                        "label": "Sandal",
                        "display_name": "Sandal",
                        "class_id": "sandal",
                        "probability": 0.02,
                    },
                ],
                "elapsed_ms": 2.4,
            },
            "comparison": {
                "agreement": True,
                "confidence_delta": 0.31,
                "test_accuracy_delta": 0.28,
                "winner": "optimized",
                "summary": "Both models predict Sneaker.",
            },
            "diagnostics": {
                "input_width": float(image.width),
                "input_height": float(image.height),
                "border_mean": 0.0,
                "polarity_inverted": False,
                "preprocessing": "dark-background-28x28",
            },
        }


@pytest.fixture
def benchmark_file(tmp_path):
    catalogue = garment_catalogue()
    trial_base = {
        "trial_id": "quickstart-baseline",
        "name": "PyTorch Quickstart Baseline MLP",
        "role": "baseline",
        "architecture": "QuickstartMLP",
        "optimizer": "SGD",
        "learning_rate": 0.001,
        "batch_size": 64,
        "epochs": 5,
        "scheduler": "none",
        "weight_decay": 0.0,
        "augmentation": "none",
        "dropout": 0.0,
        "best_val_accuracy": 0.65,
        "test_accuracy": 0.65,
        "train_seconds": 10.0,
        "parameter_count": 669706,
    }
    trial_opt = {
        **trial_base,
        "trial_id": "convnet-adamw-64ch",
        "name": "HPO 5 · ConvNet",
        "role": "optimized",
        "architecture": "GarmentConvNet",
        "optimizer": "AdamW",
        "epochs": 20,
        "scheduler": "CosineAnnealingLR",
        "augmentation": "Flip+Affine",
        "dropout": 0.25,
        "best_val_accuracy": 0.935,
        "test_accuracy": 0.93,
    }
    payload = {
        "dataset": "FashionMNIST",
        "generated_at": "2026-11-15T00:00:00+00:00",
        "device": "cpu",
        "baseline": trial_base,
        "optimized": trial_opt,
        "trials": [trial_base, trial_opt],
        "per_class_accuracy": [
            {
                "class_index": item["class_index"],
                "id": item["id"],
                "label": item["label"],
                "display_name": item["display_name"],
                "category_group": item["category_group"],
                "baseline_accuracy": 0.65,
                "optimized_accuracy": 0.93,
                "delta": 0.28,
            }
            for item in catalogue
        ],
        "epoch_history": {"baseline": [], "optimized": []},
    }
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def config(tmp_path):
    return replace(
        Settings(),
        load_model=False,
        cache_dir=tmp_path / "models",
        data_dir=tmp_path / "data",
    )


@pytest.fixture
def engine():
    return FakeGarmentClassifier()


@pytest.fixture
def client(config, engine, benchmark_file):
    with TestClient(
        create_app(config, engine, benchmark_path=benchmark_file), base_url="http://localhost"
    ) as client:
        yield client


@pytest.fixture
def png_bytes():
    output = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 10, 10)).save(output, "PNG")
    return output.getvalue()


@pytest.fixture
def jpeg_bytes():
    output = io.BytesIO()
    Image.new("RGB", (64, 64), (20, 20, 20)).save(output, "JPEG")
    return output.getvalue()
