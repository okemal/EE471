# Preliminary Task Guide · PyTorch Basics (`Task-pre-demo.avi`)

This guide prepares the **max 5-minute** video explaining the preliminary PyTorch concepts from `Week-7-InClass-Exercise.pdf`:
- Tensors
- Datasets & DataLoaders
- Transforms
- Building a Neural Network
- Optimizing the Model
- Saving & Loading Weights
- Training a Small Neural Network to Classify Images

## Live Terminal Demonstration

Run the accompanying script while screen recording:

```bash
cd "Week 7/garment_id"
uv run --frozen python scripts/preliminary_basics_demo.py
```

## Talking Points (Under 5 Minutes)

1. **Tensors (`0:00 – 0:45`)**: Multidimensional numerical arrays supporting automatic differentiation (`autograd`) and hardware acceleration (`.to("cuda")` vs CPU). Show input batch shape `(N, 1, 28, 28)`.
2. **Datasets & DataLoaders (`0:45 – 1:30`)**: `torchvision.datasets.FashionMNIST` abstracts sample retrieval `(image, label)`; `DataLoader(..., batch_size=64, shuffle=True)` yields mini-batches for stochastic gradient descent.
3. **Transforms (`1:30 – 2:15`)**: `ToTensor()` scales uint8 pixels `[0, 255]` into float tensors `[0.0, 1.0]`. Normalization centers inputs by dataset mean/std (`0.2860 / 0.3530`), and training augmentations (`RandomHorizontalFlip`, `RandomAffine`) prevent overfitting.
4. **Building a Neural Network (`2:15 – 3:05`)**: Subclass `nn.Module`, flatten 28×28 pixels (`nn.Flatten`) in `QuickstartMLP`, or extract spatial features with `nn.Conv2d`, `nn.BatchNorm2d`, `nn.GELU`, and `nn.MaxPool2d` in `GarmentConvNet`.
5. **Optimizing the Model (`3:05 – 4:05`)**: `CrossEntropyLoss` measures divergence between predicted logits and true class indices; `optimizer.zero_grad()`, `loss.backward()`, and `optimizer.step()` update weights iteratively. Contrast baseline `SGD(lr=1e-3)` against `AdamW + CosineAnnealingLR`.
6. **Save & Load (`4:05 – 4:45`)**: Persist `model.state_dict()` with `safetensors`, verify SHA-256 checksums before loading (`backend/app/model.py`), and switch to `model.eval()` + `torch.inference_mode()` during serving.
