# EE471 Week 7 — Baseline vs. HPO Classifier Performance Report

Full compiled 1-page PDF: [week7_performance_report.pdf](report/week7_performance_report.pdf) ([LaTeX source](report/week7_performance_report.tex)).

## Executive Comparison

| Task & Dataset | Baseline Model | Baseline Test Acc | Optimized HPO Model | Optimized Test Acc | Gain |
|---|---|---:|---|---:|---:|
| Task 1 — FashionMNIST (`28x28` gray, 10 classes) | `QuickstartMLP` (`669,706` params, SGD `lr=0.001`, 5 ep) | `64.28%` | `GarmentConvNet` (`1,868,746` params, AdamW `lr=0.001`, 20 ep) | **`94.61%`** | **`+30.33 pp`** |
| Task 2 — CIFAR-10 (`32x32` RGB, 10 classes) | `TutorialCifarNet` (`62,006` params, SGD `lr=0.001`, batch `4`, 2 ep) | `55.80%` | `CifarResNet9` (`3,699,514` params, AdamW `lr=0.0025`, 26 ep) | **`92.49%`** | **`+36.69 pp`** |

All models were trained on an NVIDIA GeForce RTX 4050 Laptop GPU with stratified train/validation splits and evaluated once on the untouched `10,000`-image official test sets.

## Task 1 (`garment_id` — FashionMNIST) HPO Progression

| Trial ID | Architecture | Optimizer / LR | Epochs / Batch | Regularization & Augmentations | Val Acc | Test Acc |
|---|---|---|---|---|---:|---:|
| `quickstart-baseline` | `QuickstartMLP` | SGD `0.001` | `5` / `64` | None | `0.6422` | `0.6428` |
| `mlp-tuned-lr` | `QuickstartMLP` | SGD `0.01` | `10` | None | `0.8472` | `0.8396` |
| `mlp-sgd-momentum` | `QuickstartMLP` | SGD+Mom `0.9` / StepLR | `15` | Tuned momentum & decay | `0.8910` | `0.8861` |
| `mlp-adamw-cosine` | `QuickstartMLP` | AdamW `0.001` / Cosine | `15` / `32` | AdamW decoupled decay + Cosine LR | `0.9002` | `0.8996` |
| `convnet-sgd-32ch` | `GarmentConvNet` (32ch) | SGD+Mom | `15` | HorizontalFlip | `0.9422` | `0.9373` |
| **`convnet-adamw-64ch`** | **`GarmentConvNet` (64ch)** | **AdamW `0.001` / Cosine** | **`20`** | **Flip+Affine, Dropout `0.25`, LS `0.05`** | **`0.9503`** | **`0.9461`** |

- **Largest Per-Class Gains**: `Sandal` (`0.011 -> 0.987`, `+97.6 pp`; baseline got only `11` right, misclassifying `524` as Sneaker and `440` as Ankle boot) and `Shirt` (`0.068 -> 0.823`, `+75.5 pp`; baseline misclassified `315` as Coat, `248` as Pullover, and `246` as T-shirt/top). `Coat` (`+38.6 pp`) and `Pullover` (`+31.4 pp`) also recovered sharply.

## Task 2 (`cifar10_id` — CIFAR-10) HPO Progression

| Trial ID | Architecture | Optimizer / LR | Epochs / Batch | Regularization & Augmentations | Val Acc | Test Acc |
|---|---|---|---|---|---:|---:|
| `tutorial-baseline` | `TutorialCifarNet` | SGD `0.001` | `2` / `4` | None | `0.5722` | `0.5580` |
| `cifarnet-adamw-hpo` | `TutorialCifarNet` | AdamW `0.0015` / Cosine | `15` / `64` | HorizontalFlip, WD `1e-4` | `0.6672` | `0.6683` |
| `resnet9-sgd-32ch` | `CifarResNet9` (32ch) | SGD `0.05` / Cosine | `18` / `128` | Flip+Crop, WD `5e-4`, Dropout `0.10` | `0.8828` | `0.8808` |
| `resnet9-adamw-32ch` | `CifarResNet9` (32ch) | AdamW `0.002` / Cosine | `22` / `128` | Flip+Crop, WD `5e-4`, Dropout `0.15` | `0.9236` | `0.9158` |
| **`resnet9-adamw-48ch`** | **`CifarResNet9` (48ch)** | **AdamW `0.0025` / Cosine** | **`26` / `128`** | **Flip+Crop+Cutout, WD `5e-4`, Dropout `0.20`** | **`0.9312`** | **`0.9249`** |

- **Largest Per-Class Gains**: `Deer` (`0.347 -> 0.932`, `+58.5 pp`), `Cat` (`0.268 -> 0.834`, `+56.6 pp`; baseline got only `268` right, confusing `221` with `dog` and `145` with `frog`), `Bird` (`0.442 -> 0.887`, `+44.5 pp`), `Dog` (`0.464 -> 0.882`, `+41.8 pp`), and `Truck` (`0.547 -> 0.948`, `+40.1 pp`; `truck -> car` confusion cut from `230` to `30`).

## Why Hyperparameter Optimization (HPO) Matters

Across both datasets, structured HPO separated three distinct sources of error that a default tutorial training recipe conflates:

1. **Optimizer & LR Scaling First Unlock Baseline Capacity**: Holding architecture fixed, increasing learning rate, switching to Momentum/AdamW, extending epochs, and adding cosine annealing raised `QuickstartMLP` by `+25.68 pp` (`64.28% -> 89.96%`) and `TutorialCifarNet` by `+11.03 pp` (`55.80% -> 66.83%`). Default small learning rates and short schedules leave weights severely under-converged (causing `11/1000` `Sandal` collapse on FashionMNIST and `268/1000` `Cat` collapse on CIFAR-10).
2. **Spatial Inductive Bias Breaks Fixed-Capacity Ceilings**: Once optimizer hyperparameters saturate (`~90%` on `QuickstartMLP`, `~67%` on 2-conv `TutorialCifarNet`), spatial feature hierarchies (`GarmentConvNet`, `CifarResNet9` with BatchNorm + GELU + residual skips) unlock `+4.65 pp` on FashionMNIST and `+25.66 pp` on CIFAR-10.
3. **Regularization & Augmentation Prevent Overfitting in Higher-Capacity CNNs**: Combining `Flip+Affine`, `Flip+Crop+Cutout`, decoupled weight decay (`5e-4`), dropout (`0.20–0.25`), and label smoothing (`0.05`) keeps validation/test generalization tight (`95.03% -> 94.61%` on FashionMNIST; `93.12% -> 92.49%` on CIFAR-10).
