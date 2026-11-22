"""Offline geometry, config, and live model tests for Week 8 Task 2 arm-pose classifier."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from arm_pose.classifier import (
    LEFT_ELBOW,
    LEFT_HIP,
    LEFT_SHOULDER,
    LEFT_WRIST,
    RIGHT_ELBOW,
    RIGHT_HIP,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
    ArmPoseClassifier,
    classify_pose_landmarks,
)
from arm_pose.config import ArmPoseConfig, InvalidImageError, load_rgb_image, verify_model_file
from arm_pose.visualize import save_annotated_pose

INPUT_PHOTOS = Path(__file__).resolve().parents[2] / "input_photos"


def _make_landmarks(
    *,
    left_elbow_y: float = 0.52,
    left_wrist_y: float = 0.65,
    right_elbow_y: float = 0.52,
    right_wrist_y: float = 0.65,
    left_vis: float = 0.99,
    right_vis: float = 0.99,
    left_shoulder_y: float = 0.35,
    right_shoulder_y: float = 0.35,
) -> list[SimpleNamespace]:
    lms = [SimpleNamespace(x=0.5, y=0.5, z=0.0, visibility=0.95) for _ in range(33)]
    lms[LEFT_SHOULDER] = SimpleNamespace(x=0.60, y=left_shoulder_y, z=0.0, visibility=left_vis)
    lms[RIGHT_SHOULDER] = SimpleNamespace(x=0.40, y=right_shoulder_y, z=0.0, visibility=right_vis)
    lms[LEFT_ELBOW] = SimpleNamespace(x=0.63, y=left_elbow_y, z=0.0, visibility=left_vis)
    lms[RIGHT_ELBOW] = SimpleNamespace(x=0.37, y=right_elbow_y, z=0.0, visibility=right_vis)
    lms[LEFT_WRIST] = SimpleNamespace(x=0.65, y=left_wrist_y, z=0.0, visibility=left_vis)
    lms[RIGHT_WRIST] = SimpleNamespace(x=0.35, y=right_wrist_y, z=0.0, visibility=right_vis)
    lms[LEFT_HIP] = SimpleNamespace(x=0.57, y=0.65, z=0.0, visibility=0.98)
    lms[RIGHT_HIP] = SimpleNamespace(x=0.43, y=0.65, z=0.0, visibility=0.98)
    return lms


def test_classify_all_four_arm_states():
    down = classify_pose_landmarks(_make_landmarks())
    assert down.label == "None"
    assert down.pose_detected is True

    left_up = classify_pose_landmarks(_make_landmarks(left_elbow_y=0.22, left_wrist_y=0.10))
    assert left_up.label == "left"
    assert left_up.left is not None and left_up.left.is_up is True
    assert left_up.right is not None and left_up.right.is_up is False

    right_up = classify_pose_landmarks(_make_landmarks(right_elbow_y=0.22, right_wrist_y=0.10))
    assert right_up.label == "right"

    both_up = classify_pose_landmarks(
        _make_landmarks(
            left_elbow_y=0.22, left_wrist_y=0.10, right_elbow_y=0.20, right_wrist_y=0.08
        )
    )
    assert both_up.label == "both"
    assert both_up.to_dict()["label"] == "both"


def test_edge_cases_chest_fist_tilted_torso_low_visibility_and_empty():
    # No pose detected -> "None"
    empty = classify_pose_landmarks([])
    assert empty.label == "None" and empty.pose_detected is False

    # Bent chest-level fist on left while right arm is raised overhead (like pose-2.jpg)
    chest_pump = classify_pose_landmarks(
        _make_landmarks(
            right_elbow_y=0.26,
            right_wrist_y=0.12,
            left_elbow_y=0.47,
            left_wrist_y=0.34,
        )
    )
    assert chest_pump.label == "right"

    # Strongly tilted torso with anatomical left arm reaching overhead (like pose-1.jpg)
    tilted = classify_pose_landmarks(
        _make_landmarks(
            left_shoulder_y=0.42,
            right_shoulder_y=0.35,
            left_elbow_y=0.25,
            left_wrist_y=0.14,
            right_elbow_y=0.52,
            right_wrist_y=0.66,
        )
    )
    assert tilted.label == "left"

    # Low visibility on raised wrist should not trigger false positive
    occluded = classify_pose_landmarks(
        _make_landmarks(left_elbow_y=0.20, left_wrist_y=0.08, left_vis=0.10)
    )
    assert occluded.label == "None"


def test_config_validation_and_safe_image_loading(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        verify_model_file(tmp_path / "missing.task", "abc")

    fake_model = tmp_path / "model.task"
    fake_model.write_bytes(b"weights")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_model_file(fake_model, "0" * 64)
    assert verify_model_file(fake_model, "", verify_hash=False) == fake_model

    with pytest.raises(InvalidImageError, match="does not exist"):
        load_rgb_image(tmp_path / "nope.jpg")

    empty = tmp_path / "empty.jpg"
    empty.write_bytes(b"")
    with pytest.raises(InvalidImageError, match="empty"):
        load_rgb_image(empty)

    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image")
    with pytest.raises(InvalidImageError, match="Could not decode"):
        load_rgb_image(bad)

    valid = tmp_path / "ok.png"
    Image.new("RGBA", (40, 30), (20, 40, 60, 255)).save(valid)
    with pytest.raises(InvalidImageError, match="exceeds"):
        load_rgb_image(valid, replace(ArmPoseConfig(), max_image_bytes=10))

    rgb = load_rgb_image(valid)
    assert rgb.shape == (30, 40, 3)

    lms = _make_landmarks(left_elbow_y=0.2, left_wrist_y=0.1)
    res = classify_pose_landmarks(lms)
    out = save_annotated_pose(rgb, lms, res, tmp_path / "annotated.png")
    assert out.is_file()


@pytest.mark.live
@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("pose-1.jpg", "left"),
        ("pose-2.jpg", "right"),
        ("pose-3.jpg", "both"),
    ],
)
def test_live_pose_images(filename: str, expected: str):
    with ArmPoseClassifier() as classifier:
        result, _, _ = classifier.predict_path(INPUT_PHOTOS / filename)
    assert result.pose_detected is True
    assert result.label == expected, result.to_dict()


@pytest.mark.live
def test_live_blank_image_returns_none():
    blank = np.full((256, 256, 3), 240, dtype=np.uint8)
    with ArmPoseClassifier() as classifier:
        result, _ = classifier.predict_rgb(blank)
    assert result.label == "None"
    assert result.pose_detected is False
