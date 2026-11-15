"""Runnable PyTorch basics walkthrough for Task-pre-demo.avi.

Covers:
1. Tensors (creation, shapes, dtypes, GPU placement)
2. Datasets & DataLoaders (FashionMNIST download, batching, shuffling)
3. Transforms (ToTensor, Normalize, data augmentation)
4. Building a neural network (nn.Module, Flatten, Linear, ReLU)
5. Optimizing the model (CrossEntropyLoss, SGD, backpropagation)
6. Saving & loading weights (safetensors & state_dict)
"""

import tempfile
from pathlib import Path

import torch
from safetensors.torch import load_file, save_file
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    print("=== 1. PyTorch Tensors ===")
    x = torch.tensor([[1.0, 2.0], [3.0, 4.0]])
    rand_x = torch.rand(2, 1, 28, 28)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Tensor shape={x.shape}, dtype={x.dtype}, device={device}")
    print(f"Random image batch shape={rand_x.shape}, moved={rand_x.to(device).device}")

    print("\n=== 2 & 3. Datasets, Transforms & DataLoaders ===")
    transform = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize((0.2860,), (0.3530,)),
        ]
    )
    data_dir = ROOT / ".cache" / "data"
    train_data = datasets.FashionMNIST(
        root=str(data_dir), train=True, download=True, transform=transform
    )
    train_loader = DataLoader(train_data, batch_size=64, shuffle=True)
    batch_images, batch_labels = next(iter(train_loader))
    print(
        f"Dataset size={len(train_data)}, batch_images={batch_images.shape}, "
        f"labels={batch_labels.shape}"
    )

    print("\n=== 4. Build Neural Network ===")

    class QuickstartDemoNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.flatten = nn.Flatten()
            self.net = nn.Sequential(
                nn.Linear(28 * 28, 512),
                nn.ReLU(),
                nn.Linear(512, 512),
                nn.ReLU(),
                nn.Linear(512, 10),
            )

        def forward(self, inputs: torch.Tensor) -> torch.Tensor:
            return self.net(self.flatten(inputs))

    model = QuickstartDemoNet().to(device)
    print(model)

    print("\n=== 5. Optimize Model (Forward + Loss + Backward + Step) ===")
    loss_fn = nn.CrossEntropyLoss()
    optimizer = torch.optim.SGD(model.parameters(), lr=1e-3)
    model.train()
    images, labels = batch_images.to(device), batch_labels.to(device)
    logits = model(images)
    loss = loss_fn(logits, labels)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    print(f"Single optimization step loss={loss.item():.4f}")

    print("\n=== 6. Save & Load Weights Safely ===")
    with tempfile.TemporaryDirectory() as tmp:
        ckpt = Path(tmp) / "demo_weights.safetensors"
        save_file(model.state_dict(), str(ckpt))
        reloaded = QuickstartDemoNet().to(device)
        reloaded.load_state_dict(load_file(str(ckpt), device=device))
        reloaded.eval()
        with torch.inference_mode():
            check_logits = reloaded(images)
        assert torch.allclose(model.eval()(images), check_logits, atol=1e-5)
        print(f"Verified lossless safetensors save & reload at {ckpt.name}")


if __name__ == "__main__":
    main()
