"""Verified local inference loader running baseline and HPO-optimized CIFAR-10 models."""

import hashlib
import json
import threading
import time
from pathlib import Path

import torch
from safetensors.torch import load_file

from .architecture import build_model, prepare_cifar_tensor
from .catalogue import cifar_catalogue
from .config import Settings
from .decision import evaluate_prediction


def resolve_device(requested: str) -> str:
    """Resolve 'auto', 'cpu', or 'cuda' safely without silent GPU fallback."""
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA was explicitly requested, but no GPU device is available.")
        return "cuda"
    if requested == "cpu":
        return "cpu"
    raise ValueError(f"Unsupported CIFAR10_ID_DEVICE value: {requested!r}")


def verify_sha256(path: Path, expected_hex: str) -> None:
    """Verify a model weight file's SHA-256 digest before loading weights."""
    if not path.exists():
        raise FileNotFoundError(f"Missing trained model weights: {path}")
    with path.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest()
    if actual != expected_hex:
        raise ValueError(f"Checkpoint checksum mismatch for {path.name}.")


class DualCifarClassifier:
    """Side-by-side inference engine for TutorialCifarNet and CifarResNet9."""

    name = "TutorialCifarNet + CifarResNet9 (PyTorch)"

    def __init__(self, config: Settings) -> None:
        self.config = config
        self.status = "loading" if config.load_model else "disabled"
        self.device = "cpu"
        self.error: str | None = None
        self.lock = threading.Lock()
        self.manifest: dict | None = None
        self.baseline_model: torch.nn.Module | None = None
        self.optimized_model: torch.nn.Module | None = None
        self.baseline_accuracy: float | None = None
        self.optimized_accuracy: float | None = None

    def load(self) -> None:
        """Load and verify both trained safetensors checkpoints from cache_dir."""
        if self.status == "disabled":
            return
        try:
            self.device = resolve_device(self.config.device)
            manifest_path = self.config.cache_dir / "manifest.json"
            if not manifest_path.exists():
                raise FileNotFoundError(
                    "Trained CIFAR-10 models were not found. Run scripts/train_models.py first."
                )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.manifest = manifest

            base_meta = manifest["baseline"]
            base_path = self.config.cache_dir / base_meta["filename"]
            verify_sha256(base_path, base_meta["sha256"])
            baseline = build_model(base_meta["architecture"], base_meta.get("params"))
            baseline.load_state_dict(load_file(str(base_path), device="cpu"))
            baseline.to(self.device).eval()

            opt_meta = manifest["optimized"]
            opt_path = self.config.cache_dir / opt_meta["filename"]
            verify_sha256(opt_path, opt_meta["sha256"])
            optimized = build_model(opt_meta["architecture"], opt_meta.get("params"))
            optimized.load_state_dict(load_file(str(opt_path), device="cpu"))
            optimized.to(self.device).eval()

            self.baseline_model = baseline
            self.optimized_model = optimized
            self.baseline_accuracy = float(base_meta["test_accuracy"])
            self.optimized_accuracy = float(opt_meta["test_accuracy"])
            self.error = None
            self.status = "ready"
        except Exception as exc:
            self.status = "error"
            self.error = str(exc)

    def _build_prediction(
        self,
        model_id: str,
        meta: dict,
        probs: list[float],
        elapsed_ms: float,
    ) -> dict:
        catalogue = cifar_catalogue()
        ranked = sorted(enumerate(probs), key=lambda pair: pair[1], reverse=True)
        top_classes = [
            {
                "label": catalogue[idx]["label"],
                "display_name": catalogue[idx]["display_name"],
                "class_id": catalogue[idx]["id"],
                "probability": round(prob, 6),
            }
            for idx, prob in ranked[:3]
        ]
        best_idx, best_prob = ranked[0]
        return {
            "model_id": model_id,
            "model_name": meta["name"],
            "architecture": meta["architecture"],
            "hyperparameters": meta["hyperparameters"],
            "test_accuracy": round(float(meta["test_accuracy"]), 4),
            "predicted_class": catalogue[best_idx]["label"],
            "predicted_display_name": catalogue[best_idx]["display_name"],
            "predicted_id": catalogue[best_idx]["id"],
            "confidence": round(float(best_prob), 6),
            "top_classes": top_classes,
            "elapsed_ms": round(elapsed_ms, 2),
        }

    def predict(self, image) -> dict:
        """Run both baseline and HPO-optimized models on a validated image."""
        if self.status != "ready" or self.baseline_model is None or self.optimized_model is None:
            raise RuntimeError("CIFAR-10 classifier models are not loaded.")
        assert self.manifest is not None
        catalogue = cifar_catalogue()

        tensor, diagnostics = prepare_cifar_tensor(image)
        tensor = tensor.to(self.device)

        with torch.inference_mode():
            t0 = time.perf_counter()
            base_logits = self.baseline_model(tensor)[0]
            base_probs = base_logits.softmax(dim=0).cpu().tolist()
            base_ms = (time.perf_counter() - t0) * 1000

            t1 = time.perf_counter()
            opt_logits = self.optimized_model(tensor)[0]
            opt_probs = opt_logits.softmax(dim=0).cpu().tolist()
            opt_ms = (time.perf_counter() - t1) * 1000

        baseline_pred = self._build_prediction(
            "baseline", self.manifest["baseline"], base_probs, base_ms
        )
        optimized_pred = self._build_prediction(
            "optimized", self.manifest["optimized"], opt_probs, opt_ms
        )

        status, message = evaluate_prediction(opt_probs, self.config)
        ranked_opt = sorted(enumerate(opt_probs), key=lambda pair: pair[1], reverse=True)
        candidates = [
            {
                "cifar_class": catalogue[idx],
                "probability": round(float(prob), 6),
                "baseline_probability": round(float(base_probs[idx]), 6),
            }
            for idx, prob in ranked_opt[:3]
        ]

        agree = baseline_pred["predicted_id"] == optimized_pred["predicted_id"]
        conf_delta = round(optimized_pred["confidence"] - baseline_pred["confidence"], 6)
        acc_delta = round(optimized_pred["test_accuracy"] - baseline_pred["test_accuracy"], 4)
        if agree:
            summary = (
                f"Both models predict {optimized_pred['predicted_display_name']}; "
                f"the optimized ResNet-9 shifts confidence by {conf_delta:+.1%} "
                f"(+{acc_delta * 100:.1f} pp test accuracy)."
            )
        else:
            summary = (
                f"Models disagree: baseline predicts {baseline_pred['predicted_display_name']} "
                f"({baseline_pred['confidence']:.1%}), while the HPO-optimized ResNet-9 predicts "
                f"{optimized_pred['predicted_display_name']} ({optimized_pred['confidence']:.1%})."
            )

        return {
            "status": status,
            "message": message,
            "candidates": candidates,
            "baseline": baseline_pred,
            "optimized": optimized_pred,
            "comparison": {
                "agreement": agree,
                "confidence_delta": conf_delta,
                "test_accuracy_delta": acc_delta,
                "winner": "optimized",
                "summary": summary,
            },
            "diagnostics": diagnostics,
        }
