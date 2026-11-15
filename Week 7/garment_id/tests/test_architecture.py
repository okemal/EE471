"""PyTorch model architecture and garment tensor preprocessing tests."""

import pytest
import torch
from PIL import Image, ImageDraw

from backend.app.architecture import (
    GarmentConvNet,
    QuickstartMLP,
    build_model,
    prepare_garment_tensor,
)


def test_models_forward_shape_and_builder():
    x = torch.rand(2, 1, 28, 28)
    mlp = build_model("QuickstartMLP")
    assert isinstance(mlp, QuickstartMLP)
    assert mlp(x).shape == (2, 10)

    cnn = build_model("GarmentConvNet", {"base_channels": 16, "hidden_dim": 64, "dropout": 0.1})
    assert isinstance(cnn, GarmentConvNet)
    assert cnn(x).shape == (2, 10)

    with pytest.raises(ValueError, match="Unsupported architecture"):
        build_model("UnknownNet")


def test_prepare_garment_tensor_dark_and_rectangular_images():
    dark_28 = Image.new("RGB", (28, 28), (5, 5, 5))
    tensor, diag = prepare_garment_tensor(dark_28)
    assert tensor.shape == (1, 1, 28, 28)
    assert 0.0 <= float(tensor.min()) <= float(tensor.max()) <= 1.0
    assert diag["polarity_inverted"] is False

    rect_dark = Image.new("RGB", (80, 40), (0, 0, 0))
    draw = ImageDraw.Draw(rect_dark)
    draw.rectangle([25, 8, 55, 32], fill=(220, 220, 220))
    tensor_rect, diag_rect = prepare_garment_tensor(rect_dark)
    assert tensor_rect.shape == (1, 1, 28, 28)
    assert float(tensor_rect.max()) > 0.5
    assert diag_rect["polarity_inverted"] is False


def test_prepare_garment_tensor_inverts_light_studio_background():
    studio = Image.new("RGB", (120, 120), (245, 245, 245))
    draw = ImageDraw.Draw(studio)
    draw.rectangle([35, 25, 85, 95], fill=(30, 30, 30))
    tensor, diag = prepare_garment_tensor(studio)
    assert tensor.shape == (1, 1, 28, 28)
    assert diag["polarity_inverted"] is True
    # Background corners stay near 0 after inversion; center foreground stays bright.
    assert float(tensor[0, 0, 0, 0]) < 0.05
    assert float(tensor[0, 0, 14, 14]) > 0.7

    blank_light = Image.new("RGB", (60, 60), (255, 255, 255))
    blank_tensor, blank_diag = prepare_garment_tensor(blank_light)
    assert blank_tensor.shape == (1, 1, 28, 28)
    assert blank_diag["polarity_inverted"] is True
