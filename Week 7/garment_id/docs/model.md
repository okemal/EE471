# Atelier Garment Classifier & HPO Study

## 1. Datasets & Splits

- **Benchmark dataset**: Zalando Research FashionMNIST (70,000 grayscale `28×28` images across 10 garment categories).
- **Tutorial Baseline split**: Full 60,000 training set trained with the official PyTorch Quickstart loop (`epochs=5`, `SGD`, `lr=0.001`, `batch=64`, no momentum, no weight decay).
- **HPO Validation split**: Stratified/permuted split (`seed=42`) of **54,000** training images and **6,000** validation images. Final checkpoint selection picks the epoch achieving peak validation accuracy (for HPO trials) and evaluates once on the **10,000** held-out test images.

## 2. Baseline vs. Optimized Architectures

1. **Baseline (`QuickstartMLP`, 669,706 parameters)**:
   - Exact replica of PyTorch Quickstart `NeuralNetwork`: `Flatten() -> Linear(784, 512) -> ReLU -> Linear(512, 512) -> ReLU -> Linear(512, 10)`.
2. **Optimized (`GarmentConvNet`, 1,868,746 parameters)**:
   - Normalized internally via `(x - 0.2860) / 0.3530` (safe against caller preprocessing mismatches).
   - Two double-conv spatial stages (`Conv2d(3×3) + BatchNorm2d + GELU` × 2, `64 -> 128` channels, `MaxPool2d(2)`, `Dropout2d`) followed by `Flatten() -> Linear(128×7×7, 256) -> BatchNorm1d -> GELU -> Dropout(0.25) -> Linear(256, 10)`.

## 3. Hyperparameter Optimization Progression

| Trial ID | Architecture | Optimizer & Schedule | LR | Batch | Epochs | Augmentation | Best Val Acc | Test Acc | Train Time |
|---|---|---|---|---|---|---|---|---|---|
| `quickstart-baseline` | `QuickstartMLP` | `SGD` | `0.001` | 64 | 5 | `none` | 64.22% | **64.28%** | 12.50s |
| `mlp-tuned-lr` | `QuickstartMLP` | `SGD` | `0.01` | 64 | 10 | `none` | 84.72% | 83.96% | 23.98s |
| `mlp-sgd-momentum` | `QuickstartMLP` | `SGD (m=0.9) + StepLR` | `0.01` | 64 | 15 | `none` | 89.10% | 88.61% | 37.42s |
| `mlp-adamw-cosine` | `QuickstartMLP` | `AdamW + CosineAnnealingLR` | `0.001` | 32 | 15 | `none` | 90.02% | 89.96% | 51.34s |
| `convnet-sgd-32ch` | `GarmentConvNet (32ch)` | `SGD (m=0.9) + Cosine` | `0.015` | 128 | 15 | `RandomHorizontalFlip` | 94.22% | 93.73% | 70.77s |
| **`convnet-adamw-64ch`** | **`GarmentConvNet (64ch)`** | **`AdamW + CosineAnnealingLR`** | **`0.001`** | **64** | **20** | **`Flip+Affine` (+LS=0.05)** | **95.03%** | **94.61%** | **313.34s** |

> [!NOTE]
> Even within the fixed 3-layer MLP (`QuickstartMLP`), HPO alone lifts test accuracy from **64.28%** to **89.96%** (+25.68 pp) by tuning learning rate, momentum/AdamW, batch size, and cosine annealing. Switching to spatial convolutions (`GarmentConvNet` with BatchNorm, GELU, `Flip+Affine` augmentation, dropout `0.25`, and label smoothing `0.05`) gains another +4.65 pp to reach **94.61%** (cutting test error rate from `35.72%` down to `5.39%` — an **84.9%** relative error reduction).

## 4. Per-Class Test Accuracy & Confusion Shifts (10,000 Test Images)

| ID | Category | Baseline Acc | Optimized Acc | Gain (pp) |
|---|---|---|---|---|
| 0 | T-shirt / Top | 77.80% | 90.50% | +12.70 |
| 1 | Trouser | 90.20% | 99.10% | +8.90 |
| 2 | Pullover | 61.50% | 92.90% | +31.40 |
| 3 | Dress | 77.10% | 95.20% | +18.10 |
| 4 | Coat | 54.10% | 92.70% | +38.60 |
| 5 | Sandal | 1.10% | 98.70% | +97.60 |
| 6 | Shirt | 6.80% | 82.30% | +75.50 |
| 7 | Sneaker | 90.30% | 98.10% | +7.80 |
| 8 | Bag | 90.70% | 99.40% | +8.70 |
| 9 | Ankle boot | 93.20% | 97.20% | +4.00 |

- In the 5-epoch Quickstart baseline, **Sandal** collapsed to `11/1000` correct (`524` misclassified as Sneaker and `440` as Ankle boot) and **Shirt** reached only `68/1000` (`315` as Coat, `248` as Pullover, `246` as T-shirt/top).
- In the HPO-optimized `GarmentConvNet`, Sandal jumps to **98.70%** (`987/1000`) and Shirt climbs to **82.30%** (`823/1000`).

## 5. Inference & Studio-Photo Preprocessing

`prepare_garment_tensor()` (`backend/app/architecture.py`) adapts arbitrary JPEG/PNG/WebP uploads cleanly to `28×28` FashionMNIST polarity:
1. Convert image to grayscale and measure mean border intensity (`_border_mean()`).
2. If border mean > `0.55` (light studio backdrop), invert pixel polarity (`ImageOps.invert`), subtract the `0.15`-quantile residual backdrop floor, rescale foreground highlights, and tightly crop/pad square around active pixels (`> 0.12`).
3. Resize bilinearly to `28×28` into `[0.0, 1.0]` before feeding both `QuickstartMLP` and `GarmentConvNet`.
