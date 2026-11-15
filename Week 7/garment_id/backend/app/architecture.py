"""PyTorch neural architectures and preprocessing for FashionMNIST garment classification."""

from typing import Any

import torch
from PIL import Image, ImageOps
from torch import nn
from torchvision.transforms import functional as TF

FASHION_MNIST_MEAN = 0.2860
FASHION_MNIST_STD = 0.3530
NUM_CLASSES = 10


class QuickstartMLP(nn.Module):
    """Exact baseline NeuralNetwork architecture from the PyTorch Quickstart tutorial."""

    def __init__(self) -> None:
        super().__init__()
        self.flatten = nn.Flatten()
        self.linear_relu_stack = nn.Sequential(
            nn.Linear(28 * 28, 512),
            nn.ReLU(),
            nn.Linear(512, 512),
            nn.ReLU(),
            nn.Linear(512, NUM_CLASSES),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Flatten 28x28 grayscale tensor in [0, 1] and produce 10 logits."""
        x = self.flatten(x)
        return self.linear_relu_stack(x)


class GarmentConvNet(nn.Module):
    """HPO-tuned convolutional network with BatchNorm and GELU for 28x28 garments."""

    def __init__(
        self,
        base_channels: int = 64,
        hidden_dim: int = 256,
        dropout: float = 0.25,
        num_classes: int = NUM_CLASSES,
    ) -> None:
        super().__init__()
        self.base_channels = base_channels
        self.hidden_dim = hidden_dim
        self.dropout_rate = dropout
        self.features = nn.Sequential(
            nn.Conv2d(1, base_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(base_channels),
            nn.GELU(),
            nn.Conv2d(base_channels, base_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(base_channels),
            nn.GELU(),
            nn.MaxPool2d(2),
            nn.Dropout2d(dropout * 0.5),
            nn.Conv2d(base_channels, base_channels * 2, kernel_size=3, padding=1),
            nn.BatchNorm2d(base_channels * 2),
            nn.GELU(),
            nn.Conv2d(base_channels * 2, base_channels * 2, kernel_size=3, padding=1),
            nn.BatchNorm2d(base_channels * 2),
            nn.GELU(),
            nn.MaxPool2d(2),
            nn.Dropout2d(dropout),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(base_channels * 2 * 7 * 7, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Normalize [0, 1] input tensor internally and produce 10 class logits."""
        normalized = (x - FASHION_MNIST_MEAN) / FASHION_MNIST_STD
        features = self.features(normalized)
        return self.classifier(features)


def build_model(architecture: str, params: dict[str, Any] | None = None) -> nn.Module:
    """Instantiate a supported garment classifier architecture from configuration."""
    params = params or {}
    if architecture == "QuickstartMLP":
        return QuickstartMLP()
    if architecture == "GarmentConvNet":
        return GarmentConvNet(
            base_channels=int(params.get("base_channels", 64)),
            hidden_dim=int(params.get("hidden_dim", 256)),
            dropout=float(params.get("dropout", 0.25)),
        )
    raise ValueError(f"Unsupported architecture: {architecture}")


def _border_mean(gray: Image.Image) -> float:
    """Compute average normalized brightness [0, 1] along the 2px image border."""
    tensor = TF.to_tensor(gray).squeeze(0)
    h, w = tensor.shape
    band = min(2, h // 4 or 1, w // 4 or 1)
    top = tensor[:band, :]
    bottom = tensor[-band:, :]
    left = tensor[:, :band]
    right = tensor[:, -band:]
    border = torch.cat([top.reshape(-1), bottom.reshape(-1), left.reshape(-1), right.reshape(-1)])
    return float(border.mean().item())


def _crop_and_pad_square(gray: Image.Image) -> Image.Image:
    """Center non-background garment pixels in a square canvas before 28x28 resize."""
    tensor = TF.to_tensor(gray).squeeze(0)
    mask = tensor > 0.12
    if not mask.any():
        return gray
    coords = torch.nonzero(mask, as_tuple=False)
    y_min, x_min = coords.min(dim=0).values.tolist()
    y_max, x_max = coords.max(dim=0).values.tolist()
    crop = gray.crop((x_min, y_min, x_max + 1, y_max + 1))
    cw, ch = crop.size
    side = max(cw, ch)
    pad = max(2, round(side * 0.14))
    canvas_side = side + 2 * pad
    canvas = Image.new("L", (canvas_side, canvas_side), 0)
    canvas.paste(crop, ((canvas_side - cw) // 2, (canvas_side - ch) // 2))
    return canvas


def prepare_garment_tensor(
    image: Image.Image,
) -> tuple[torch.Tensor, dict[str, float | bool | str]]:
    """Convert a validated RGB image into a (1, 1, 28, 28) FashionMNIST-compatible tensor."""
    gray = image.convert("L")
    border_mean = _border_mean(gray)
    inverted = border_mean > 0.55
    if inverted:
        gray = ImageOps.invert(gray)
        # Subtract residual inverted studio backdrop tint when foreground signal exists.
        tensor = TF.to_tensor(gray).squeeze(0)
        bg_level = float(torch.quantile(tensor, 0.15).item())
        shifted = torch.clamp(tensor - bg_level, min=0.0)
        peak = float(shifted.max().item())
        if peak > 0.15:
            shifted = torch.clamp(shifted / peak, 0.0, 1.0)
        gray = TF.to_pil_image(shifted)

    if gray.size != (28, 28):
        if inverted:
            gray = _crop_and_pad_square(gray)
        elif gray.width != gray.height:
            side = max(gray.size)
            square = Image.new("L", (side, side), 0)
            square.paste(gray, ((side - gray.width) // 2, (side - gray.height) // 2))
            gray = square
        gray = gray.resize((28, 28), Image.Resampling.BILINEAR)

    tensor = TF.to_tensor(gray).unsqueeze(0)
    diagnostics: dict[str, float | bool | str] = {
        "input_width": float(image.width),
        "input_height": float(image.height),
        "border_mean": round(border_mean, 4),
        "polarity_inverted": inverted,
        "preprocessing": "inverted-studio-crop-28x28" if inverted else "dark-background-28x28",
    }
    return tensor, diagnostics
