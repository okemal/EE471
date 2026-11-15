"""Unit tests for the PyTorch training, HPO trial execution, and artifact export module."""

import json

import pytest
import torch
from torch.utils.data import TensorDataset

from backend.app.architecture import QuickstartMLP
from backend.app.training import (
    TrialSpec,
    build_augmentation,
    build_optimizer,
    build_scheduler,
    run_trial,
    save_study_artifacts,
    trial_spec_to_dict,
)


def _synthetic_dataset(n: int = 30) -> TensorDataset:
    torch.manual_seed(0)
    x = torch.rand(n, 1, 28, 28)
    y = torch.arange(n) % 10
    return TensorDataset(x, y)


def test_builders_and_error_paths():
    model = QuickstartMLP()
    assert build_augmentation("none") is None
    assert build_augmentation("RandomHorizontalFlip") is not None
    assert build_augmentation("Flip+Affine") is not None
    with pytest.raises(ValueError, match="augmentation"):
        build_augmentation("unknown")

    sgd_spec = TrialSpec("t1", "T1", "baseline", "QuickstartMLP", "SGD", 1e-2, 8, 2)
    adam_spec = TrialSpec(
        "t2", "T2", "hpo_candidate", "QuickstartMLP", "AdamW", 1e-3, 8, 3, scheduler="StepLR"
    )
    cos_spec = TrialSpec(
        "t3",
        "T3",
        "optimized",
        "GarmentConvNet",
        "AdamW",
        1e-3,
        8,
        3,
        scheduler="CosineAnnealingLR",
    )
    bad_opt = TrialSpec("t4", "T4", "hpo_candidate", "QuickstartMLP", "RMSprop", 1e-3, 8, 2)
    bad_sch = TrialSpec(
        "t5", "T5", "hpo_candidate", "QuickstartMLP", "SGD", 1e-3, 8, 2, scheduler="MagicLR"
    )

    opt_sgd = build_optimizer(model, sgd_spec)
    opt_adam = build_optimizer(model, adam_spec)
    assert build_scheduler(opt_sgd, sgd_spec) is None
    assert build_scheduler(opt_adam, adam_spec) is not None
    assert build_scheduler(opt_adam, cos_spec) is not None
    assert trial_spec_to_dict(sgd_spec)["trial_id"] == "t1"

    with pytest.raises(ValueError, match="optimizer"):
        build_optimizer(model, bad_opt)
    with pytest.raises(ValueError, match="scheduler"):
        build_scheduler(opt_sgd, bad_sch)


def test_run_trial_and_save_artifacts_on_synthetic_data(tmp_path):
    train_ds = _synthetic_dataset(24)
    val_ds = _synthetic_dataset(12)
    test_ds = _synthetic_dataset(12)

    base_spec = TrialSpec(
        trial_id="base",
        name="Base",
        role="baseline",
        architecture="QuickstartMLP",
        optimizer="SGD",
        learning_rate=1e-2,
        batch_size=8,
        epochs=2,
    )
    opt_spec = TrialSpec(
        trial_id="opt",
        name="Opt",
        role="optimized",
        architecture="GarmentConvNet",
        optimizer="AdamW",
        learning_rate=1e-3,
        batch_size=8,
        epochs=2,
        scheduler="CosineAnnealingLR",
        augmentation="Flip+Affine",
        dropout=0.1,
        base_channels=8,
        hidden_dim=16,
    )

    base_res = run_trial(base_spec, train_ds, val_ds, test_ds, device="cpu")
    opt_res = run_trial(opt_spec, train_ds, val_ds, test_ds, device="cpu")
    assert len(base_res["history"]) == 2
    assert len(opt_res["test_metrics"]["per_class_accuracy"]) == 10

    cache_dir = tmp_path / "models"
    bench_path = tmp_path / "benchmark.json"
    eval_path = tmp_path / "evaluation.json"
    report = save_study_artifacts(
        cache_dir=cache_dir,
        benchmark_output=bench_path,
        evaluation_output=eval_path,
        baseline_result=base_res,
        optimized_result=opt_res,
        all_records=[base_res["record"], opt_res["record"]],
        device="cpu",
    )
    assert (cache_dir / "baseline.safetensors").exists()
    assert (cache_dir / "optimized.safetensors").exists()
    assert (cache_dir / "manifest.json").exists()
    assert len(report["per_class_accuracy"]) == 10
    eval_json = json.loads(eval_path.read_text(encoding="utf-8"))
    assert len(eval_json["optimized_confusion_matrix"]) == 10
