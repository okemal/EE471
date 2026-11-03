"""Cache the assignment's official TorchVision ResNet50 weights before offline use."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.config import settings  # noqa: E402
from backend.app.resnet import checkpoint_path  # noqa: E402

if __name__ == "__main__":
    print(f"ResNet50 IMAGENET1K_V1 ready: {checkpoint_path(settings)}")
