"""Shared pytest fixtures and deterministic test double for CIFAR-10 API tests."""

import io
import json
import threading
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.catalogue import cifar_catalogue
from backend.app.config import Settings
from backend.app.main import create_app


class FakeCifarClassifier:
    """Model-independent test double matching the DualCifarClassifier contract."""

    name = "TutorialCifarNet + CifarResNet9 (Test)"
    status = "ready"
    device = "cpu"
    error = None
    baseline_accuracy = 0.56
    optimized_accuracy = 0.91

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
        catalogue = cifar_catalogue()
        return {
            "status": "matched",
            "message": "Confident CIFAR-10 category match from the optimized ResNet-9.",
            "candidates": [
                {
                    "cifar_class": catalogue[0],
                    "probability": 0.92,
                    "baseline_probability": 0.64,
                },
                {
                    "cifar_class": catalogue[8],
                    "probability": 0.05,
                    "baseline_probability": 0.21,
                },
                {
                    "cifar_class": catalogue[2],
                    "probability": 0.02,
                    "baseline_probability": 0.10,
                },
            ],
            "baseline": {
                "model_id": "baseline",
                "model_name": "PyTorch CIFAR-10 Tutorial Baseline Net",
                "architecture": "TutorialCifarNet",
                "hyperparameters": {
                    "optimizer": "SGD",
                    "learning_rate": 0.001,
                    "batch_size": 4,
                    "epochs": 2,
                },
                "test_accuracy": 0.56,
                "predicted_class": "plane",
                "predicted_display_name": "Airplane",
                "predicted_id": "airplane",
                "confidence": 0.64,
                "top_classes": [
                    {
                        "label": "plane",
                        "display_name": "Airplane",
                        "class_id": "airplane",
                        "probability": 0.64,
                    },
                    {
                        "label": "ship",
                        "display_name": "Ship",
                        "class_id": "ship",
                        "probability": 0.21,
                    },
                    {
                        "label": "bird",
                        "display_name": "Bird",
                        "class_id": "bird",
                        "probability": 0.10,
                    },
                ],
                "elapsed_ms": 1.4,
            },
            "optimized": {
                "model_id": "optimized",
                "model_name": "HPO-Optimized ResNet-9",
                "architecture": "CifarResNet9",
                "hyperparameters": {
                    "optimizer": "AdamW",
                    "learning_rate": 0.0025,
                    "batch_size": 128,
                    "epochs": 26,
                },
                "test_accuracy": 0.91,
                "predicted_class": "plane",
                "predicted_display_name": "Airplane",
                "predicted_id": "airplane",
                "confidence": 0.92,
                "top_classes": [
                    {
                        "label": "plane",
                        "display_name": "Airplane",
                        "class_id": "airplane",
                        "probability": 0.92,
                    },
                    {
                        "label": "ship",
                        "display_name": "Ship",
                        "class_id": "ship",
                        "probability": 0.05,
                    },
                    {
                        "label": "bird",
                        "display_name": "Bird",
                        "class_id": "bird",
                        "probability": 0.02,
                    },
                ],
                "elapsed_ms": 3.1,
            },
            "comparison": {
                "agreement": True,
                "confidence_delta": 0.28,
                "test_accuracy_delta": 0.35,
                "winner": "optimized",
                "summary": "Both models predict Airplane.",
            },
            "diagnostics": {
                "input_width": float(image.width),
                "input_height": float(image.height),
                "center_cropped": False,
                "preprocessing": "bicubic-32x32",
            },
        }


@pytest.fixture
def benchmark_file(tmp_path):
    catalogue = cifar_catalogue()
    trial_base = {
        "trial_id": "tutorial-baseline",
        "name": "PyTorch CIFAR-10 Tutorial Baseline Net",
        "role": "baseline",
        "architecture": "TutorialCifarNet",
        "optimizer": "SGD",
        "learning_rate": 0.001,
        "batch_size": 4,
        "epochs": 2,
        "scheduler": "none",
        "weight_decay": 0.0,
        "augmentation": "none",
        "dropout": 0.0,
        "best_val_accuracy": 0.55,
        "test_accuracy": 0.56,
        "train_seconds": 8.0,
        "parameter_count": 62006,
    }
    trial_opt = {
        **trial_base,
        "trial_id": "resnet9-adamw-48ch",
        "name": "HPO 4 · ResNet-9",
        "role": "optimized",
        "architecture": "CifarResNet9",
        "optimizer": "AdamW",
        "batch_size": 128,
        "epochs": 26,
        "scheduler": "CosineAnnealingLR",
        "augmentation": "Flip+Crop+Cutout",
        "dropout": 0.2,
        "best_val_accuracy": 0.915,
        "test_accuracy": 0.91,
    }
    payload = {
        "dataset": "CIFAR-10",
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
                "baseline_accuracy": 0.56,
                "optimized_accuracy": 0.91,
                "delta": 0.35,
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
    return FakeCifarClassifier()


@pytest.fixture
def client(config, engine, benchmark_file):
    with TestClient(
        create_app(config, engine, benchmark_path=benchmark_file), base_url="http://localhost"
    ) as client:
        yield client


@pytest.fixture
def png_bytes():
    output = io.BytesIO()
    Image.new("RGB", (64, 64), (30, 80, 140)).save(output, "PNG")
    return output.getvalue()


@pytest.fixture
def jpeg_bytes():
    output = io.BytesIO()
    Image.new("RGB", (64, 64), (40, 90, 150)).save(output, "JPEG")
    return output.getvalue()
