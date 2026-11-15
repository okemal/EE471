# Model Training & HPO Benchmarks — Vision10 (`cifar10_id`)

`Vision10` pairs two CIFAR-10 PyTorch classifiers built on `32x32` RGB inputs (`CIFAR10_MEAN = (0.4914, 0.4822, 0.4465)`, `CIFAR10_STD = (0.2470, 0.2435, 0.2616)`):

1. **Baseline (`tutorial-baseline` — `TutorialCifarNet`)**: Mirrors the PyTorch CIFAR-10 tutorial convolutional network (`Conv(3->6, 5x5) -> Pool -> Conv(6->16, 5x5) -> Pool -> FC(400->120->84->10)` with internal `[-1, 1]` scaling `(x - 0.5) / 0.5`), trained with SGD (`lr=0.001`, `momentum=0.9`, `batch_size=4`, `epochs=2`, no scheduler, no data augmentation). Parameters: `62,006`.
2. **Optimized (`resnet9-adamw-48ch` — `CifarResNet9`)**: Residual convolutional network with `prep (3->48)`, `layer1 (48->96, pool)` + `ResidualBlock(96)`, `layer2 (96->192, pool)`, `layer3 (192->384, pool)` + `ResidualBlock(384)`, and `AdaptiveMaxPool2d(1) -> Flatten -> Dropout(0.2) -> Linear(384->10)`, using `Conv2d(3x3, bias=False) -> BatchNorm2d -> GELU` blocks and channel-wise CIFAR-10 buffer normalization. Parameters: `3,699,514`.

Training uses a stratified `45,000` train / `5,000` validation split (`seed=42`) from CIFAR-10 (`50,000` training images) and evaluates untouched against the `10,000`-image CIFAR-10 test set on an NVIDIA GeForce RTX 4050 Laptop GPU (`--device cuda`).

## HPO Progression (`5` Trials)

| Trial ID | Model | Optimizer | LR | Batch | Epochs | Scheduler | Weight Decay | Augmentation | Dropout | Val Acc | Test Acc | Time (s) | Params |
|---|---|---|---|---:|---:|---|---:|---|---:|---:|---:|---:|---:|
| `tutorial-baseline` | `TutorialCifarNet` | `SGD` | `0.001` | `4` | `2` | `none` | `0.0` | `none` | `0.0` | `0.5722` | `0.5580` | `17.92` | `62,006` |
| `cifarnet-adamw-hpo` | `TutorialCifarNet` | `AdamW` | `0.0015` | `64` | `15` | `CosineAnnealingLR` | `0.0001` | `HorizontalFlip` | `0.0` | `0.6672` | `0.6683` | `9.60` | `62,006` |
| `resnet9-sgd-32ch` | `CifarResNet9` | `SGD` | `0.05` | `128` | `18` | `CosineAnnealingLR` | `0.0005` | `Flip+Crop` | `0.1` | `0.8828` | `0.8808` | `137.81` | `1,646,122` |
| `resnet9-adamw-32ch` | `CifarResNet9` | `AdamW` | `0.002` | `128` | `22` | `CosineAnnealingLR` | `0.0005` | `Flip+Crop` | `0.15` | `0.9236` | `0.9158` | `169.73` | `1,646,122` |
| **`resnet9-adamw-48ch`** | **`CifarResNet9`** | **`AdamW`** | **`0.0025`** | **`128`** | **`26`** | **`CosineAnnealingLR`** | **`0.0005`** | **`Flip+Crop+Cutout`** | **`0.2`** | **`0.9312`** | **`0.9249`** | `376.82` | `3,699,514` |

Overall test accuracy gain: **`55.80% -> 92.49%`** (**`+36.69` percentage points**).

### Learning Trajectory Highlights

- `tutorial-baseline`: Epoch 1 (`train_acc=0.3816`, `val_acc=0.4840`) -> Epoch 2 (`train_acc=0.5237`, `val_acc=0.5722`), severely undertrained due to `2` epochs and small `batch_size=4`.
- `cifarnet-adamw-hpo`: Keeping the exact `62,006`-parameter `TutorialCifarNet` architecture while tuning optimizer (`AdamW`), batch size (`64`), `15` epochs, `CosineAnnealingLR`, and horizontal flip raised test accuracy to `0.6683` (`+11.03 pp`), showing the ceiling of the tiny 2-conv network without residual depth or normalization.
- `CifarResNet9` (`32ch` -> `48ch`) + `Flip+Crop+Cutout` + `AdamW` (`lr=0.0025`, `CosineAnnealingLR`): jumped from `0.6683` to `0.8808` (`SGD`) -> `0.9158` (`AdamW 32ch`) -> **`0.9249`** (`AdamW 48ch` + Cutout; Epoch 26 `train_loss=0.3633`, `train_acc=0.9820`, `val_loss=0.23467`, `val_acc=0.9304`).

## Per-Class Test Accuracy (`1,000` Samples per Class)

| Class (`label`) | Group | Baseline (`TutorialCifarNet`) | Optimized (`CifarResNet9`) | Delta |
|---|---|---:|---:|---:|
| Airplane (`plane`) | Vehicles | `0.645` | `0.943` | `+0.298` |
| Automobile (`car`) | Vehicles | `0.754` | `0.976` | `+0.222` |
| Bird (`bird`) | Animals | `0.442` | `0.887` | `+0.445` |
| Cat (`cat`) | Animals | `0.268` | `0.834` | `+0.566` |
| Deer (`deer`) | Animals | `0.347` | `0.932` | `+0.585` |
| Dog (`dog`) | Animals | `0.464` | `0.882` | `+0.418` |
| Frog (`frog`) | Animals | `0.734` | `0.954` | `+0.220` |
| Horse (`horse`) | Animals | `0.730` | `0.941` | `+0.211` |
| Ship (`ship`) | Vehicles | `0.649` | `0.952` | `+0.303` |
| Truck (`truck`) | Vehicles | `0.547` | `0.948` | `+0.401` |

### Key Confusion Matrix Improvements (`baseline -> optimized`)

- **Cat (`cat`)**: Baseline identified only `268 / 1,000` cats correctly, confusing `221` with `dog`, `145` with `frog`, `109` with `horse`, and `99` with `bird`. Optimized `CifarResNet9` recovers `834 / 1,000` (`+56.6 pp`, with `74` remaining `cat -> dog` confusions).
- **Deer (`deer`)**: Baseline identified only `347 / 1,000` deer (`167` misclassified as `horse`, `150` as `frog`, `139` as `bird`); optimized `CifarResNet9` lifts `deer` accuracy to `932 / 1,000` (`+58.5 pp`).
- **Truck vs. Automobile (`truck` / `car`)**: Baseline misclassified `230 / 1,000` trucks as `car`; `CifarResNet9` reduces `truck -> car` errors to `30 / 1,000` (`0.547 -> 0.948`).
- **Bird (`bird`)**: Baseline scattered predictions across natural backgrounds (`96` as `frog`, `91` as `deer`, `78` as `plane`); `CifarResNet9` increases `bird` accuracy from `0.442` to `0.887` (`+44.5 pp`).

Full trial metrics and confusion matrices are stored in [benchmark.json](../backend/app/data/benchmark.json) and [evaluation.json](evaluation.json).
