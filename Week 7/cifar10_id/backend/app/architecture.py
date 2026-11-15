"""PyTorch neural architectures and preprocessing for CIFAR-10 image classification."""

from typing import Any

import torch
import torch.nn.functional as F
from PIL import Image
from torch import nn
from torchvision.transforms import functional as TF

CIFAR10_MEAN = (0.4914, 0.4822, 0.4465)
CIFAR10_STD = (0.2470, 0.2435, 0.2616)
NUM_CLASSES = 10


class TutorialCifarNet(nn.Module):
    """Exact baseline Net architecture from the PyTorch CIFAR-10 tutorial."""

    def __init__(self) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(3, 6, 5)
        self.pool = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(6, 16, 5)
        self.fc1 = nn.Linear(16 * 5 * 5, 120)
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, NUM_CLASSES)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Normalize [0, 1] RGB tensor to [-1, 1] and produce 10 logits."""
        x = (x - 0.5) / 0.5
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = torch.flatten(x, 1)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)


def _conv_bn_gelu(in_ch: int, out_ch: int, pool: bool = False) -> nn.Sequential:
    layers: list[nn.Module] = [
        nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1, bias=False),
        nn.BatchNorm2d(out_ch),
        nn.GELU(),
    ]
    if pool:
        layers.append(nn.MaxPool2d(2))
    return nn.Sequential(*layers)


class ResidualBlock(nn.Module):
    """Two-layer 3x3 residual block preserving spatial dimensions."""

    def __init__(self, channels: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            _conv_bn_gelu(channels, channels),
            _conv_bn_gelu(channels, channels),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply residual skip addition."""
        return x + self.block(x)


class CifarResNet9(nn.Module):
    """HPO-tuned ResNet-9 convolutional classifier for 32x32 CIFAR-10 RGB images."""

    mean: torch.Tensor
    std: torch.Tensor

    def __init__(
        self,
        base_channels: int = 48,
        dropout: float = 0.2,
        num_classes: int = NUM_CLASSES,
    ) -> None:
        super().__init__()
        self.base_channels = base_channels
        self.dropout_rate = dropout
        self.register_buffer("mean", torch.tensor(CIFAR10_MEAN).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor(CIFAR10_STD).view(1, 3, 1, 1))

        self.prep = _conv_bn_gelu(3, base_channels)
        self.layer1 = _conv_bn_gelu(base_channels, base_channels * 2, pool=True)
        self.res1 = ResidualBlock(base_channels * 2)
        self.layer2 = _conv_bn_gelu(base_channels * 2, base_channels * 4, pool=True)
        self.layer3 = _conv_bn_gelu(base_channels * 4, base_channels * 8, pool=True)
        self.res2 = ResidualBlock(base_channels * 8)
        self.classifier = nn.Sequential(
            nn.AdaptiveMaxPool2d(1),
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(base_channels * 8, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Normalize [0, 1] RGB tensor internally and produce 10 logits."""
        out = (x - self.mean) / self.std
        out = self.prep(out)
        out = self.res1(self.layer1(out))
        out = self.layer2(out)
        out = self.res2(self.layer3(out))
        return self.classifier(out)


def build_model(architecture: str, params: dict[str, Any] | None = None) -> nn.Module:
    """Instantiate a supported CIFAR-10 classifier architecture from configuration."""
    params = params or {}
    if architecture == "TutorialCifarNet":
        return TutorialCifarNet()
    if architecture == "CifarResNet9":
        return CifarResNet9(
            base_channels=int(params.get("base_channels", 48)),
            dropout=float(params.get("dropout", 0.2)),
        )
    raise ValueError(f"Unsupported architecture: {architecture}")


def prepare_cifar_tensor(
    image: Image.Image,
) -> tuple[torch.Tensor, dict[str, float | bool | str]]:
    """Convert a validated RGB image into a (1, 3, 32, 32) tensor in [0, 1]."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    cropped = False
    if max(width, height) / min(width, height) > 1.25:
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        rgb = rgb.crop((left, top, left + side, top + side))
        cropped = True

    if rgb.size != (32, 32):
        rgb = rgb.resize((32, 32), Image.Resampling.BICUBIC)
        preprocessing = "center-crop-bicubic-32x32" if cropped else "bicubic-32x32"
    else:
        preprocessing = "native-32x32-rgb"

    tensor = TF.to_tensor(rgb).unsqueeze(0)
    diagnostics: dict[str, float | bool | str] = {
        "input_width": float(width),
        "input_height": float(height),
        "center_cropped": cropped,
        "preprocessing": preprocessing,
    }
    return tensor, diagnostics
