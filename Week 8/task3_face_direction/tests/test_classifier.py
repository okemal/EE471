"""Offline geometry, config, and live model tests for Week 8 Task 3 face direction classifier."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from face_direction.classifier import (
    LEFT_FACE_EDGE_IDX,
    NOSE_TIP_IDX,
    RIGHT_FACE_EDGE_IDX,
    FaceDirectionClassifier,
    NoFaceDetectedError,
    classify_face_signals,
    compute_landmark_asymmetry,
    compute_viewer_gaze_score,
    extract_head_pose_degrees,
)
from face_direction.config import (
    FaceDirectionConfig,
    InvalidImageError,
    load_rgb_image,
    verify_model_file,
)
from face_direction.visualize import save_annotated_face

INPUT_PHOTOS = Path(__file__).resolve().parents[2] / "input_photos"


def _yaw_matrix(yaw_deg: float, pitch_deg: float = 0.0, roll_deg: float = 0.0) -> np.ndarray:
    """Build a synthetic 4x4 transformation matrix with known yaw/pitch/roll angles."""
    y = math.radians(yaw_deg)
    p = math.radians(pitch_deg)
    r = math.radians(roll_deg)
    ry = np.array(
        [[math.cos(y), 0.0, math.sin(y)], [0.0, 1.0, 0.0], [-math.sin(y), 0.0, math.cos(y)]]
    )
    rx = np.array(
        [[1.0, 0.0, 0.0], [0.0, math.cos(p), -math.sin(p)], [0.0, math.sin(p), math.cos(p)]]
    )
    rz = np.array(
        [[math.cos(r), -math.sin(r), 0.0], [math.sin(r), math.cos(r), 0.0], [0.0, 0.0, 1.0]]
    )
    mat = np.eye(4, dtype=np.float64)
    mat[:3, :3] = ry @ rx @ rz
    return mat


def _make_landmarks(nose_x: float = 0.50) -> list[SimpleNamespace]:
    lms = [SimpleNamespace(x=0.50, y=0.50, z=0.0) for _ in range(478)]
    lms[LEFT_FACE_EDGE_IDX] = SimpleNamespace(x=0.25, y=0.50, z=0.0)
    lms[RIGHT_FACE_EDGE_IDX] = SimpleNamespace(x=0.75, y=0.50, z=0.0)
    lms[NOSE_TIP_IDX] = SimpleNamespace(x=nose_x, y=0.52, z=-0.05)
    return lms


def _make_blendshapes(**values: float) -> list[SimpleNamespace]:
    return [SimpleNamespace(category_name=k, score=v) for k, v in values.items()]


def test_head_pose_matrix_classification_left_right_straight():
    lms = _make_landmarks(nose_x=0.50)

    left = classify_face_signals(lms, transform_matrix=_yaw_matrix(-34.0, pitch_deg=3.0))
    assert left.direction == "left"
    assert left.signal_source == "pose_matrix"
    assert left.yaw_deg is not None and left.yaw_deg < -30.0

    right = classify_face_signals(lms, transform_matrix=_yaw_matrix(32.0, roll_deg=-4.0))
    assert right.direction == "right"
    assert right.signal_source == "pose_matrix"
    assert right.yaw_deg is not None and right.yaw_deg > 28.0

    straight = classify_face_signals(lms, transform_matrix=_yaw_matrix(-2.0, pitch_deg=5.0))
    assert straight.direction == "straight"
    assert straight.signal_source == "pose_matrix"
    assert straight.to_dict()["direction"] == "straight"


def test_landmark_asymmetry_fallback_and_gaze_override():
    assert classify_face_signals(_make_landmarks(nose_x=0.35)).direction == "left"
    assert classify_face_signals(_make_landmarks(nose_x=0.65)).direction == "right"
    assert classify_face_signals(_make_landmarks(nose_x=0.50)).direction == "straight"

    # Head straight (~0 deg) but strong eye glance toward viewer's right
    gaze_right = _make_blendshapes(
        eyeLookInLeft=0.80, eyeLookOutRight=0.80, eyeLookOutLeft=0.05, eyeLookInRight=0.05
    )
    res_right = classify_face_signals(
        _make_landmarks(nose_x=0.50),
        transform_matrix=_yaw_matrix(0.0),
        blendshapes=gaze_right,
    )
    assert res_right.direction == "right"
    assert res_right.signal_source == "gaze_blendshapes"

    # Head straight (~0 deg) without matrix, strong eye glance toward viewer's left
    gaze_left = _make_blendshapes(
        eyeLookOutLeft=0.85, eyeLookInRight=0.85, eyeLookInLeft=0.02, eyeLookOutRight=0.02
    )
    res_left = classify_face_signals(_make_landmarks(nose_x=0.50), blendshapes=gaze_left)
    assert res_left.direction == "left"
    assert res_left.signal_source == "gaze_blendshapes"
    assert compute_viewer_gaze_score(None) == 0.0


def test_validation_errors_and_annotation(tmp_path: Path):
    with pytest.raises(ValueError, match="4x4"):
        extract_head_pose_degrees(np.eye(3))
    with pytest.raises(ValueError, match=">= 455"):
        compute_landmark_asymmetry([])

    with pytest.raises(FileNotFoundError):
        verify_model_file(tmp_path / "missing.task", "abc")

    fake_model = tmp_path / "model.task"
    fake_model.write_bytes(b"weights")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_model_file(fake_model, "0" * 64)
    assert verify_model_file(fake_model, "", verify_hash=False) == fake_model

    with pytest.raises(InvalidImageError, match="does not exist"):
        load_rgb_image(tmp_path / "missing.png")

    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    with pytest.raises(InvalidImageError, match="empty"):
        load_rgb_image(empty)

    bad = tmp_path / "bad.png"
    bad.write_bytes(b"corrupt")
    with pytest.raises(InvalidImageError, match="Could not decode"):
        load_rgb_image(bad)

    valid = tmp_path / "ok.png"
    Image.new("RGBA", (64, 64), (100, 120, 140, 255)).save(valid)
    with pytest.raises(InvalidImageError, match="exceeds"):
        load_rgb_image(valid, replace(FaceDirectionConfig(), max_image_bytes=10))

    rgb = load_rgb_image(valid)
    lms = _make_landmarks(0.35)
    res = classify_face_signals(lms, transform_matrix=_yaw_matrix(-30.0))
    out = save_annotated_face(rgb, lms, res, tmp_path / "face_ann.png")
    assert out.is_file()


@pytest.mark.live
@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("face-1.png", "left"),
        ("face-2.png", "right"),
        ("face-3.png", "straight"),
    ],
)
def test_live_face_images(filename: str, expected: str):
    with FaceDirectionClassifier() as classifier:
        result, _, _ = classifier.predict_path(INPUT_PHOTOS / filename)
    assert result.direction == expected, result.to_dict()


@pytest.mark.live
def test_live_blank_image_raises_no_face():
    blank = np.full((256, 256, 3), 240, dtype=np.uint8)
    with FaceDirectionClassifier() as classifier:
        with pytest.raises(NoFaceDetectedError):
            classifier.predict_rgb(blank)
