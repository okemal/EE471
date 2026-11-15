"""PyTorch model architecture and CIFAR-10 tensor preprocessing tests."""

import pytest
import torch
from PIL import Image

from backend.app.architecture import (
    CifarResNet9,
    TutorialCifarNet,
    build_model,
    prepare_cifar_tensor,
)


def test_models_forward_shape_and_builder():
    x = torch.rand(2, 3, 32, 32)
    base = build_model("TutorialCifarNet")
    assert isinstance(base, TutorialCifarNet)
    assert base(x).shape == (2, 10)

    opt = build_model("CifarResNet9", {"base_channels": 16, "dropout": 0.1})
    assert isinstance(opt, CifarResNet9)
    assert opt(x).shape == (2, 10)

    with pytest.raises(ValueError, match="Unsupported architecture"):
        build_model("UnknownNet")


def test_prepare_cifar_tensor_native_square_and_wide_crop():
    native = Image.new("RGB", (32, 32), (100, 150, 200))
    t_native, d_native = prepare_cifar_tensor(native)
    assert t_native.shape == (1, 3, 32, 32)
    assert 0.0 <= float(t_native.min()) <= float(t_native.max()) <= 1.0
    assert d_native["center_cropped"] is False
    assert d_native["preprocessing"] == "native-32x32-rgb"

    square = Image.new("RGB", (128, 128), (50, 120, 200))
    t_sq, d_sq = prepare_cifar_tensor(square)
    assert t_sq.shape == (1, 3, 32, 32)
    assert d_sq["center_cropped"] is False
    assert d_sq["preprocessing"] == "bicubic-32x32"

    wide = Image.new("RGB", (160, 80), (40, 80, 120))
    t_wide, d_wide = prepare_cifar_tensor(wide)
    assert t_wide.shape == (1, 3, 32, 32)
    assert d_wide["center_cropped"] is True
    assert d_wide["preprocessing"] == "center-crop-bicubic-32x32"
