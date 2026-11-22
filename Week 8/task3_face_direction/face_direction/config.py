"""Configuration, model SHA-256 verification, and safe image loading for Task 3."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_FILENAME = "face_landmarker.task"
MODEL_URL = (
    "https://huggingface.co/litert-community/MediaPipe-FaceLandmarker/"
    "resolve/main/face_landmarker.task"
)
MODEL_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"

Image.MAX_IMAGE_PIXELS = 25_000_000


class InvalidImageError(ValueError):
    """Raised when an input image is missing, oversized, unreadable, or unsupported."""


@dataclass(frozen=True)
class FaceDirectionConfig:
    """Runtime settings and angular thresholds for viewer-relative looking direction."""

    model_path: Path = PROJECT_ROOT / "models" / MODEL_FILENAME
    expected_sha256: str = MODEL_SHA256
    verify_sha256: bool = True
    max_image_bytes: int = 10 * 1024 * 1024
    min_face_detection_confidence: float = 0.5
    yaw_threshold_deg: float = 12.0
    asymmetry_threshold: float = 0.18
    gaze_override_threshold: float = 0.45

    @classmethod
    def from_env(cls) -> FaceDirectionConfig:
        """Build configuration from environment overrides while keeping safe defaults."""
        env_model = os.environ.get("FACE_DIRECTION_MODEL_PATH")
        return cls(
            model_path=Path(env_model) if env_model else PROJECT_ROOT / "models" / MODEL_FILENAME,
            verify_sha256=os.environ.get("FACE_DIRECTION_SKIP_SHA256") != "1",
        )


settings = FaceDirectionConfig.from_env()


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_file(path: Path, expected_sha256: str, *, verify_hash: bool = True) -> Path:
    """Validate that the FaceLandmarker task bundle exists and matches its expected SHA-256."""
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(
            f"FaceLandmarker model missing at {resolved}. Run `python scripts/download_model.py`."
        )
    if verify_hash and expected_sha256:
        actual = sha256_file(resolved)
        if actual != expected_sha256:
            raise ValueError(
                f"SHA-256 mismatch for {resolved}: expected {expected_sha256}, got {actual}"
            )
    return resolved


def load_rgb_image(path: Path, config: FaceDirectionConfig = settings) -> np.ndarray:
    """Validate and decode a local image file into a contiguous uint8 RGB NumPy array."""
    resolved = Path(path)
    if not resolved.is_file():
        raise InvalidImageError(f"Input image does not exist: {resolved}")
    size = resolved.stat().st_size
    if size == 0:
        raise InvalidImageError(f"Input image is empty: {resolved}")
    if size > config.max_image_bytes:
        raise InvalidImageError(f"Input image exceeds {config.max_image_bytes} bytes: {size} bytes")
    try:
        with Image.open(resolved) as img:
            if (img.format or "").upper() not in {"JPEG", "PNG", "WEBP", "BMP"}:
                raise InvalidImageError(f"Unsupported image format: {img.format!r}")
            rgb = ImageOps.exif_transpose(img).convert("RGB")
            return np.ascontiguousarray(np.array(rgb, dtype=np.uint8))
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImageError(f"Could not decode image {resolved}: {exc}") from exc
