"""Model loading, checksum verification, device resolution, and dual inference tests."""

import hashlib
import json
from dataclasses import replace

import pytest
import torch
from PIL import Image
from safetensors.torch import save_file

from backend.app.architecture import GarmentConvNet, QuickstartMLP
from backend.app.config import Settings
from backend.app.model import DualGarmentClassifier, resolve_device, verify_sha256


def _sha256(path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _write_test_checkpoints(cache_dir, *, same_winner: bool = True):
    cache_dir.mkdir(parents=True, exist_ok=True)
    mlp = QuickstartMLP()
    cnn = GarmentConvNet(base_channels=8, hidden_dim=16, dropout=0.1)
    with torch.no_grad():
        for p in mlp.parameters():
            p.zero_()
        for p in cnn.parameters():
            p.zero_()
        # Bias class 7 (Sneaker) on CNN, and either class 7 or class 6 on MLP
        mlp.linear_relu_stack[-1].bias[7 if same_winner else 6] = 4.0
        cnn.classifier[-1].bias[7] = 4.0

    base_path = cache_dir / "baseline.safetensors"
    opt_path = cache_dir / "optimized.safetensors"
    save_file(mlp.state_dict(), str(base_path))
    save_file(cnn.state_dict(), str(opt_path))
    manifest = {
        "dataset": "FashionMNIST",
        "baseline": {
            "filename": "baseline.safetensors",
            "sha256": _sha256(base_path),
            "name": "Baseline MLP",
            "architecture": "QuickstartMLP",
            "params": {},
            "hyperparameters": {
                "optimizer": "SGD",
                "learning_rate": 0.001,
                "batch_size": 64,
                "epochs": 5,
            },
            "test_accuracy": 0.65,
        },
        "optimized": {
            "filename": "optimized.safetensors",
            "sha256": _sha256(opt_path),
            "name": "Optimized CNN",
            "architecture": "GarmentConvNet",
            "params": {"base_channels": 8, "hidden_dim": 16, "dropout": 0.1},
            "hyperparameters": {
                "optimizer": "AdamW",
                "learning_rate": 0.001,
                "batch_size": 64,
                "epochs": 20,
            },
            "test_accuracy": 0.93,
        },
    }
    (cache_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return base_path, opt_path


def test_resolve_device_and_settings_from_env(monkeypatch):
    assert resolve_device("cpu") == "cpu"
    assert resolve_device("auto") in {"cpu", "cuda"}
    with pytest.raises(ValueError):
        resolve_device("tpu")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert resolve_device("auto") == "cpu"
    with pytest.raises(RuntimeError, match="CUDA"):
        resolve_device("cuda")

    monkeypatch.setenv("GARMENT_ID_DEVICE", "cpu")
    monkeypatch.setenv("GARMENT_ID_OFFLINE", "1")
    env_cfg = Settings.from_env()
    assert env_cfg.device == "cpu"
    assert env_cfg.offline is True


def test_verify_sha256_and_error_states(tmp_path, config):
    missing = tmp_path / "missing.safetensors"
    with pytest.raises(FileNotFoundError):
        verify_sha256(missing, "0" * 64)

    target = tmp_path / "weights.bin"
    target.write_bytes(b"hello")
    verify_sha256(target, _sha256(target))
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_sha256(target, "0" * 64)

    disabled = DualGarmentClassifier(replace(config, load_model=False))
    disabled.load()
    assert disabled.status == "disabled"
    with pytest.raises(RuntimeError, match="not loaded"):
        disabled.predict(Image.new("RGB", (28, 28)))

    missing_manifest = DualGarmentClassifier(replace(config, load_model=True, device="cpu"))
    missing_manifest.load()
    assert missing_manifest.status == "error"


def test_dual_classifier_agree_and_disagree_predictions(config):
    _write_test_checkpoints(config.cache_dir, same_winner=True)
    engine = DualGarmentClassifier(replace(config, load_model=True, device="cpu"))
    engine.load()
    assert engine.status == "ready"
    res = engine.predict(Image.new("RGB", (28, 28), (10, 10, 10)))
    assert res["comparison"]["agreement"] is True
    assert res["optimized"]["predicted_id"] == "sneaker"
    assert res["baseline"]["predicted_id"] == "sneaker"

    _write_test_checkpoints(config.cache_dir, same_winner=False)
    engine2 = DualGarmentClassifier(replace(config, load_model=True, device="cpu"))
    engine2.load()
    res2 = engine2.predict(Image.new("RGB", (28, 28), (10, 10, 10)))
    assert res2["comparison"]["agreement"] is False
    assert "Models disagree" in res2["comparison"]["summary"]
