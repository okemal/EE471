"""PyTorch training, hyperparameter optimization, and evaluation for CIFAR-10."""

import hashlib
import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from safetensors.torch import save_file
from torch import nn
from torch.utils.data import DataLoader, Dataset, TensorDataset
from torchvision import datasets

from .architecture import NUM_CLASSES, build_model
from .catalogue import cifar_catalogue

SUPPORTED_AUGMENTATIONS = {"none", "HorizontalFlip", "Flip+Crop", "Flip+Crop+Cutout"}


@dataclass(frozen=True)
class TrialSpec:
    """Hyperparameter configuration for one CIFAR-10 training experiment."""

    trial_id: str
    name: str
    role: str
    architecture: str
    optimizer: str
    learning_rate: float
    batch_size: int
    epochs: int
    scheduler: str = "none"
    momentum: float = 0.0
    weight_decay: float = 0.0
    augmentation: str = "none"
    dropout: float = 0.0
    base_channels: int = 48
    label_smoothing: float = 0.0


DEFAULT_TRIALS: tuple[TrialSpec, ...] = (
    TrialSpec(
        trial_id="tutorial-baseline",
        name="PyTorch CIFAR-10 Tutorial Baseline Net",
        role="baseline",
        architecture="TutorialCifarNet",
        optimizer="SGD",
        learning_rate=1e-3,
        batch_size=4,
        epochs=2,
        scheduler="none",
        momentum=0.9,
        weight_decay=0.0,
        augmentation="none",
        dropout=0.0,
    ),
    TrialSpec(
        trial_id="cifarnet-adamw-hpo",
        name="HPO 1 · Tutorial Net + AdamW + Flip",
        role="hpo_candidate",
        architecture="TutorialCifarNet",
        optimizer="AdamW",
        learning_rate=1.5e-3,
        batch_size=64,
        epochs=15,
        scheduler="CosineAnnealingLR",
        weight_decay=1e-4,
        augmentation="HorizontalFlip",
        dropout=0.0,
    ),
    TrialSpec(
        trial_id="resnet9-sgd-32ch",
        name="HPO 2 · ResNet-9 (32ch) SGD+Momentum",
        role="hpo_candidate",
        architecture="CifarResNet9",
        optimizer="SGD",
        learning_rate=0.05,
        batch_size=128,
        epochs=18,
        scheduler="CosineAnnealingLR",
        momentum=0.9,
        weight_decay=5e-4,
        augmentation="Flip+Crop",
        dropout=0.1,
        base_channels=32,
    ),
    TrialSpec(
        trial_id="resnet9-adamw-32ch",
        name="HPO 3 · ResNet-9 (32ch) AdamW + Crop",
        role="hpo_candidate",
        architecture="CifarResNet9",
        optimizer="AdamW",
        learning_rate=2e-3,
        batch_size=128,
        epochs=22,
        scheduler="CosineAnnealingLR",
        weight_decay=5e-4,
        augmentation="Flip+Crop",
        dropout=0.15,
        base_channels=32,
        label_smoothing=0.05,
    ),
    TrialSpec(
        trial_id="resnet9-adamw-48ch",
        name="HPO 4 · ResNet-9 (48ch) AdamW + Cutout + Cosine",
        role="optimized",
        architecture="CifarResNet9",
        optimizer="AdamW",
        learning_rate=2.5e-3,
        batch_size=128,
        epochs=26,
        scheduler="CosineAnnealingLR",
        weight_decay=5e-4,
        augmentation="Flip+Crop+Cutout",
        dropout=0.2,
        base_channels=48,
        label_smoothing=0.05,
    ),
)


def set_seed(seed: int = 42) -> None:
    """Set deterministic seeds for Python and PyTorch CPU/CUDA RNGs."""
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def validate_augmentation(name: str) -> str:
    """Validate and return a supported tensor augmentation policy name."""
    if name not in SUPPORTED_AUGMENTATIONS:
        raise ValueError(f"Unsupported augmentation policy: {name}")
    return name


def apply_batch_augmentation(inputs: torch.Tensor, policy: str) -> torch.Tensor:
    """Apply vectorized CIFAR-10 tensor augmentations on CPU or CUDA."""
    validate_augmentation(policy)
    if policy == "none":
        return inputs

    b, _, h, w = inputs.shape
    flip_mask = torch.rand((b, 1, 1, 1), device=inputs.device) < 0.5
    out = torch.where(flip_mask, torch.flip(inputs, dims=[3]), inputs)

    if policy in {"Flip+Crop", "Flip+Crop+Cutout"}:
        pad = min(4, h - 1, w - 1)
        if pad > 0:
            padded = F.pad(out, (pad, pad, pad, pad), mode="reflect")
            ys = torch.randint(0, 2 * pad + 1, (b, 1, 1), device=out.device)
            xs = torch.randint(0, 2 * pad + 1, (b, 1, 1), device=out.device)
            y_idx = ys + torch.arange(h, device=out.device).view(1, h, 1)
            x_idx = xs + torch.arange(w, device=out.device).view(1, 1, w)
            batch_idx = torch.arange(b, device=out.device).view(b, 1, 1)
            out = (
                padded.permute(0, 2, 3, 1)[batch_idx, y_idx, x_idx].permute(0, 3, 1, 2).contiguous()
            )

    if policy == "Flip+Crop+Cutout":
        cut = min(8, h, w)
        cy = torch.randint(0, max(1, h - cut + 1), (b, 1, 1), device=out.device)
        cx = torch.randint(0, max(1, w - cut + 1), (b, 1, 1), device=out.device)
        gy = torch.arange(h, device=out.device).view(1, h, 1)
        gx = torch.arange(w, device=out.device).view(1, 1, w)
        hole = ((gy >= cy) & (gy < cy + cut) & (gx >= cx) & (gx < cx + cut)).unsqueeze(1)
        apply_cut = torch.rand((b, 1, 1, 1), device=out.device) < 0.75
        out = torch.where(hole & apply_cut, torch.zeros_like(out), out)

    return out


def build_optimizer(model: nn.Module, spec: TrialSpec) -> torch.optim.Optimizer:
    """Create the optimizer prescribed by a TrialSpec."""
    if spec.optimizer == "SGD":
        return torch.optim.SGD(
            model.parameters(),
            lr=spec.learning_rate,
            momentum=spec.momentum,
            weight_decay=spec.weight_decay,
        )
    if spec.optimizer == "AdamW":
        return torch.optim.AdamW(
            model.parameters(),
            lr=spec.learning_rate,
            weight_decay=spec.weight_decay,
        )
    raise ValueError(f"Unsupported optimizer: {spec.optimizer}")


def build_scheduler(
    optimizer: torch.optim.Optimizer, spec: TrialSpec
) -> torch.optim.lr_scheduler.LRScheduler | None:
    """Create the learning-rate scheduler prescribed by a TrialSpec."""
    if spec.scheduler == "none":
        return None
    if spec.scheduler == "StepLR":
        return torch.optim.lr_scheduler.StepLR(
            optimizer, step_size=max(1, spec.epochs // 3), gamma=0.3
        )
    if spec.scheduler == "CosineAnnealingLR":
        return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, spec.epochs))
    raise ValueError(f"Unsupported scheduler: {spec.scheduler}")


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    loss_fn: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: str,
    augmentation: str = "none",
) -> tuple[float, float]:
    """Run one training epoch and return (mean_loss, accuracy)."""
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    for inputs, targets in loader:
        inputs = apply_batch_augmentation(inputs.to(device), augmentation)
        targets = targets.to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(inputs)
        loss = loss_fn(logits, targets)
        loss.backward()
        optimizer.step()

        batch_len = targets.size(0)
        total_loss += float(loss.item()) * batch_len
        correct += int((logits.argmax(dim=1) == targets).sum().item())
        total += batch_len
    return total_loss / max(1, total), correct / max(1, total)


def evaluate_loader(
    model: nn.Module,
    loader: DataLoader,
    loss_fn: nn.Module,
    device: str,
    num_classes: int = NUM_CLASSES,
) -> dict[str, Any]:
    """Evaluate a model on a DataLoader and return accuracy, loss, and confusion matrix."""
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    confusion = [[0 for _ in range(num_classes)] for _ in range(num_classes)]
    with torch.inference_mode():
        for inputs, targets in loader:
            inputs = inputs.to(device)
            targets = targets.to(device)
            logits = model(inputs)
            loss = loss_fn(logits, targets)
            preds = logits.argmax(dim=1)

            batch_len = targets.size(0)
            total_loss += float(loss.item()) * batch_len
            correct += int((preds == targets).sum().item())
            total += batch_len

            for true_idx, pred_idx in zip(
                targets.cpu().tolist(), preds.cpu().tolist(), strict=True
            ):
                confusion[int(true_idx)][int(pred_idx)] += 1

    per_class = []
    for idx in range(num_classes):
        row_total = sum(confusion[idx])
        per_class.append(round(confusion[idx][idx] / max(1, row_total), 4))

    return {
        "loss": round(total_loss / max(1, total), 5),
        "accuracy": round(correct / max(1, total), 4),
        "confusion_matrix": confusion,
        "per_class_accuracy": per_class,
        "total": total,
    }


def _iter_tensor_batches(
    x: torch.Tensor, y: torch.Tensor, batch_size: int, shuffle: bool, seed: int, epoch: int
):
    n = x.size(0)
    if shuffle:
        perm = torch.randperm(
            n, generator=torch.Generator(device=x.device).manual_seed(seed + epoch), device=x.device
        )
        for start in range(0, n, batch_size):
            idx = perm[start : start + batch_size]
            yield x[idx], y[idx]
    else:
        for start in range(0, n, batch_size):
            yield x[start : start + batch_size], y[start : start + batch_size]


def run_trial(
    spec: TrialSpec,
    train_dataset: Dataset,
    val_dataset: Dataset,
    test_dataset: Dataset,
    device: str,
    seed: int = 42,
) -> dict[str, Any]:
    """Train one TrialSpec, retain best validation weights, and evaluate on test_dataset."""
    set_seed(seed)
    validate_augmentation(spec.augmentation)
    model_params = {
        "base_channels": spec.base_channels,
        "dropout": spec.dropout,
    }
    model = build_model(spec.architecture, model_params).to(device)
    param_count = sum(p.numel() for p in model.parameters())

    use_tensor_fastpath = isinstance(train_dataset, TensorDataset)
    generator = torch.Generator().manual_seed(seed)
    train_loader = DataLoader(
        train_dataset, batch_size=spec.batch_size, shuffle=True, generator=generator
    )
    val_loader = DataLoader(val_dataset, batch_size=256, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=256, shuffle=False)

    loss_fn = nn.CrossEntropyLoss(label_smoothing=spec.label_smoothing)
    eval_loss_fn = nn.CrossEntropyLoss()
    optimizer = build_optimizer(model, spec)
    scheduler = build_scheduler(optimizer, spec)

    best_val_acc = -1.0
    best_state: dict[str, torch.Tensor] | None = None
    history: list[dict[str, int | float]] = []

    if use_tensor_fastpath:
        tx, ty = (t.to(device) for t in train_dataset.tensors)
        vx, vy = (
            (t.to(device) for t in val_dataset.tensors)
            if isinstance(val_dataset, TensorDataset)
            else (None, None)
        )
    else:
        tx = ty = vx = vy = None

    start = time.perf_counter()
    for epoch in range(1, spec.epochs + 1):
        if tx is not None and ty is not None:
            model.train()
            total_loss = 0.0
            correct = 0
            total = 0
            for bx, by in _iter_tensor_batches(tx, ty, spec.batch_size, True, seed, epoch):
                aug_x = apply_batch_augmentation(bx, spec.augmentation)
                optimizer.zero_grad(set_to_none=True)
                logits = model(aug_x)
                loss = loss_fn(logits, by)
                loss.backward()
                optimizer.step()
                bs = by.size(0)
                total_loss += float(loss.item()) * bs
                correct += int((logits.argmax(dim=1) == by).sum().item())
                total += bs
            train_loss = total_loss / max(1, total)
            train_acc = correct / max(1, total)
        else:
            train_loss, train_acc = train_one_epoch(
                model, train_loader, loss_fn, optimizer, device, augmentation=spec.augmentation
            )
        if scheduler is not None:
            scheduler.step()
        if vx is not None and vy is not None:
            val_metrics = evaluate_loader(
                model,
                list(_iter_tensor_batches(vx, vy, 256, False, seed, epoch)),
                eval_loss_fn,
                device,  # type: ignore[arg-type]
            )
        else:
            val_metrics = evaluate_loader(model, val_loader, eval_loss_fn, device)
        val_acc = float(val_metrics["accuracy"])
        if val_acc >= best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        history.append(
            {
                "epoch": epoch,
                "train_loss": round(train_loss, 4),
                "train_accuracy": round(train_acc, 4),
                "val_loss": val_metrics["loss"],
                "val_accuracy": val_acc,
            }
        )
    train_seconds = round(time.perf_counter() - start, 2)

    assert best_state is not None
    # Keep final epoch weights for the exact 2-epoch tutorial baseline;
    # for HPO trials, restore the best validation checkpoint.
    if spec.role != "baseline":
        model.load_state_dict({k: v.to(device) for k, v in best_state.items()})
    else:
        best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    test_metrics = evaluate_loader(model, test_loader, eval_loss_fn, device)

    record = {
        "trial_id": spec.trial_id,
        "name": spec.name,
        "role": spec.role,
        "architecture": spec.architecture,
        "optimizer": spec.optimizer,
        "learning_rate": spec.learning_rate,
        "batch_size": spec.batch_size,
        "epochs": spec.epochs,
        "scheduler": spec.scheduler,
        "weight_decay": spec.weight_decay,
        "augmentation": spec.augmentation,
        "dropout": spec.dropout,
        "best_val_accuracy": round(best_val_acc, 4),
        "test_accuracy": float(test_metrics["accuracy"]),
        "train_seconds": train_seconds,
        "parameter_count": int(param_count),
    }

    return {
        "record": record,
        "state_dict": best_state,
        "model_params": model_params if spec.architecture == "CifarResNet9" else {},
        "test_metrics": test_metrics,
        "history": history,
    }


def _file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def save_study_artifacts(
    cache_dir: Path,
    benchmark_output: Path,
    evaluation_output: Path,
    baseline_result: dict[str, Any],
    optimized_result: dict[str, Any],
    all_records: list[dict[str, Any]],
    device: str,
) -> dict[str, Any]:
    """Persist trained safetensors checkpoints, SHA-256 manifest, and benchmark reports."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = cache_dir / "baseline.safetensors"
    optimized_path = cache_dir / "optimized.safetensors"
    save_file(baseline_result["state_dict"], str(baseline_path))
    save_file(optimized_result["state_dict"], str(optimized_path))

    base_rec = baseline_result["record"]
    opt_rec = optimized_result["record"]

    manifest = {
        "dataset": "CIFAR-10",
        "generated_at": datetime.now(UTC).isoformat(),
        "baseline": {
            "filename": baseline_path.name,
            "sha256": _file_sha256(baseline_path),
            "name": base_rec["name"],
            "architecture": base_rec["architecture"],
            "params": baseline_result["model_params"],
            "hyperparameters": {
                "optimizer": base_rec["optimizer"],
                "learning_rate": base_rec["learning_rate"],
                "batch_size": base_rec["batch_size"],
                "epochs": base_rec["epochs"],
                "scheduler": base_rec["scheduler"],
                "augmentation": base_rec["augmentation"],
            },
            "test_accuracy": base_rec["test_accuracy"],
        },
        "optimized": {
            "filename": optimized_path.name,
            "sha256": _file_sha256(optimized_path),
            "name": opt_rec["name"],
            "architecture": opt_rec["architecture"],
            "params": optimized_result["model_params"],
            "hyperparameters": {
                "optimizer": opt_rec["optimizer"],
                "learning_rate": opt_rec["learning_rate"],
                "batch_size": opt_rec["batch_size"],
                "epochs": opt_rec["epochs"],
                "scheduler": opt_rec["scheduler"],
                "weight_decay": opt_rec["weight_decay"],
                "dropout": opt_rec["dropout"],
                "augmentation": opt_rec["augmentation"],
            },
            "test_accuracy": opt_rec["test_accuracy"],
        },
    }
    (cache_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    catalogue = cifar_catalogue()
    base_per_class = baseline_result["test_metrics"]["per_class_accuracy"]
    opt_per_class = optimized_result["test_metrics"]["per_class_accuracy"]
    per_class_rows = []
    for item in catalogue:
        idx = item["class_index"]
        b_acc = float(base_per_class[idx])
        o_acc = float(opt_per_class[idx])
        per_class_rows.append(
            {
                "class_index": idx,
                "id": item["id"],
                "label": item["label"],
                "display_name": item["display_name"],
                "category_group": item["category_group"],
                "baseline_accuracy": b_acc,
                "optimized_accuracy": o_acc,
                "delta": round(o_acc - b_acc, 4),
            }
        )

    benchmark = {
        "dataset": "CIFAR-10",
        "generated_at": manifest["generated_at"],
        "device": device,
        "baseline": base_rec,
        "optimized": opt_rec,
        "trials": all_records,
        "per_class_accuracy": per_class_rows,
        "epoch_history": {
            "baseline": baseline_result["history"],
            "optimized": optimized_result["history"],
        },
    }

    benchmark_output.parent.mkdir(parents=True, exist_ok=True)
    benchmark_output.write_text(json.dumps(benchmark, indent=2) + "\n", encoding="utf-8")

    evaluation_payload = {
        **benchmark,
        "baseline_confusion_matrix": baseline_result["test_metrics"]["confusion_matrix"],
        "optimized_confusion_matrix": optimized_result["test_metrics"]["confusion_matrix"],
    }
    evaluation_output.parent.mkdir(parents=True, exist_ok=True)
    evaluation_output.write_text(json.dumps(evaluation_payload, indent=2) + "\n", encoding="utf-8")
    return benchmark


def _cifar_tensor_dataset(raw_ds: datasets.CIFAR10) -> TensorDataset:
    x = torch.from_numpy(raw_ds.data).permute(0, 3, 1, 2).float() / 255.0
    y = torch.tensor(raw_ds.targets, dtype=torch.long)
    return TensorDataset(x, y)


def run_cifar10_study(
    data_dir: Path,
    cache_dir: Path,
    benchmark_output: Path,
    evaluation_output: Path,
    trials: tuple[TrialSpec, ...] = DEFAULT_TRIALS,
    device: str | None = None,
) -> dict[str, Any]:
    """Download CIFAR-10, train baseline + HPO sweep, and export artifacts."""
    target_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    raw_train = datasets.CIFAR10(root=str(data_dir), train=True, download=True)
    raw_test = datasets.CIFAR10(root=str(data_dir), train=False, download=True)

    full_train_ds = _cifar_tensor_dataset(raw_train)
    test_ds = _cifar_tensor_dataset(raw_test)

    set_seed(42)
    perm = torch.randperm(len(full_train_ds), generator=torch.Generator().manual_seed(42))
    train_x, train_y = (
        full_train_ds.tensors[0][perm[:45_000]],
        full_train_ds.tensors[1][perm[:45_000]],
    )
    val_x, val_y = full_train_ds.tensors[0][perm[45_000:]], full_train_ds.tensors[1][perm[45_000:]]
    train_subset = TensorDataset(train_x, train_y)
    val_subset = TensorDataset(val_x, val_y)

    results: list[dict[str, Any]] = []
    for spec in trials:
        train_ds = full_train_ds if spec.role == "baseline" else train_subset
        res = run_trial(spec, train_ds, val_subset, test_ds, device=target_device)
        results.append(res)
        rec = res["record"]
        print(
            f"[{rec['trial_id']}] val={rec['best_val_accuracy']:.4f} "
            f"test={rec['test_accuracy']:.4f} ({rec['train_seconds']:.1f}s)",
            flush=True,
        )

    baseline_res = next(r for r in results if r["record"]["role"] == "baseline")
    hpo_candidates = [r for r in results if r["record"]["role"] != "baseline"]
    optimized_res = max(hpo_candidates, key=lambda r: r["record"]["best_val_accuracy"])
    records = []
    for res in results:
        rec = dict(res["record"])
        if res is baseline_res:
            rec["role"] = "baseline"
        elif res is optimized_res:
            rec["role"] = "optimized"
        else:
            rec["role"] = "hpo_candidate"
        res["record"] = rec
        records.append(rec)

    return save_study_artifacts(
        cache_dir=cache_dir,
        benchmark_output=benchmark_output,
        evaluation_output=evaluation_output,
        baseline_result=baseline_res,
        optimized_result=optimized_res,
        all_records=records,
        device=target_device,
    )


def trial_spec_to_dict(spec: TrialSpec) -> dict[str, Any]:
    """Serialize a TrialSpec dataclass for logging or inspection."""
    return asdict(spec)
