"""Pose-landmark geometry and MediaPipe PoseLandmarker wrapper for arm-up classification."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import mediapipe as mp
import numpy as np

from arm_pose.config import ArmPoseConfig, load_rgb_image, settings, verify_model_file

ArmLabel = Literal["left", "right", "both", "None"]

# Standard MediaPipe 33-point anatomical pose landmark indices.
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24


@dataclass(frozen=True)
class ArmMetrics:
    """Normalized vertical elevation diagnostics for a single anatomical arm."""

    side: Literal["left", "right"]
    is_up: bool
    wrist_above: float
    elbow_above: float
    shoulder_visibility: float
    wrist_visibility: float


@dataclass(frozen=True)
class ArmPoseResult:
    """Structured prediction output alongside the exact required label string."""

    label: ArmLabel
    pose_detected: bool
    torso_scale: float
    left: ArmMetrics | None
    right: ArmMetrics | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to a JSON-compatible dictionary."""
        return asdict(self)


def _landmark_visibility(landmark: Any) -> float:
    vis = getattr(landmark, "visibility", None)
    return 1.0 if vis is None else float(vis)


def _evaluate_arm(
    side: Literal["left", "right"],
    shoulder: Any,
    elbow: Any,
    wrist: Any,
    torso_scale: float,
    config: ArmPoseConfig,
) -> ArmMetrics:
    """Evaluate whether a single anatomical arm is raised above shoulder height."""
    shoulder_vis = _landmark_visibility(shoulder)
    wrist_vis = _landmark_visibility(wrist)
    # In MediaPipe normalized image space, y=0 is top and y=1 is bottom.
    wrist_above = (float(shoulder.y) - float(wrist.y)) / torso_scale
    elbow_above = (float(shoulder.y) - float(elbow.y)) / torso_scale

    visible = shoulder_vis >= config.min_visibility and wrist_vis >= config.min_visibility
    is_up = visible and (
        wrist_above > config.wrist_above_threshold
        and (
            elbow_above > config.elbow_above_threshold
            or wrist_above > config.overhead_wrist_threshold
        )
    )
    return ArmMetrics(
        side=side,
        is_up=is_up,
        wrist_above=round(wrist_above, 4),
        elbow_above=round(elbow_above, 4),
        shoulder_visibility=round(shoulder_vis, 4),
        wrist_visibility=round(wrist_vis, 4),
    )


def classify_pose_landmarks(
    landmarks: Sequence[Any] | None,
    config: ArmPoseConfig = settings,
) -> ArmPoseResult:
    """Classify raised arm(s) from 33 anatomical MediaPipe pose landmarks.

    Uses subject-anatomical perspective (matching MediaPipe's LEFT/RIGHT landmarks):
    - `"left"`: subject's left arm raised
    - `"right"`: subject's right arm raised
    - `"both"`: both arms raised
    - `"None"`: neither arm raised or no valid pose detected
    """
    if not landmarks or len(landmarks) <= RIGHT_HIP:
        return ArmPoseResult(
            label="None",
            pose_detected=False,
            torso_scale=0.0,
            left=None,
            right=None,
        )

    l_sh = landmarks[LEFT_SHOULDER]
    r_sh = landmarks[RIGHT_SHOULDER]
    l_hip = landmarks[LEFT_HIP]
    r_hip = landmarks[RIGHT_HIP]

    vertical_torso = 0.5 * (float(l_hip.y) + float(r_hip.y)) - 0.5 * (float(l_sh.y) + float(r_sh.y))
    shoulder_span = math.hypot(float(l_sh.x) - float(r_sh.x), float(l_sh.y) - float(r_sh.y))
    torso_scale = max(vertical_torso, shoulder_span, 0.10)

    left_metrics = _evaluate_arm(
        "left", l_sh, landmarks[LEFT_ELBOW], landmarks[LEFT_WRIST], torso_scale, config
    )
    right_metrics = _evaluate_arm(
        "right", r_sh, landmarks[RIGHT_ELBOW], landmarks[RIGHT_WRIST], torso_scale, config
    )

    if left_metrics.is_up and right_metrics.is_up:
        label: ArmLabel = "both"
    elif left_metrics.is_up:
        label = "left"
    elif right_metrics.is_up:
        label = "right"
    else:
        label = "None"

    return ArmPoseResult(
        label=label,
        pose_detected=True,
        torso_scale=round(torso_scale, 4),
        left=left_metrics,
        right=right_metrics,
    )


class ArmPoseClassifier:
    """Stateful MediaPipe PoseLandmarker inference engine for single-image arm classification."""

    def __init__(self, config: ArmPoseConfig = settings) -> None:
        self.config = config
        self._landmarker: mp.tasks.vision.PoseLandmarker | None = None

    def load(self) -> None:
        """Verify model SHA-256 and initialize MediaPipe PoseLandmarker on CPU."""
        if self._landmarker is not None:
            return
        model_file = verify_model_file(
            self.config.model_path,
            self.config.expected_sha256,
            verify_hash=self.config.verify_sha256,
        )
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=str(model_file),
                delegate=mp.tasks.BaseOptions.Delegate.CPU,
            ),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=self.config.min_pose_detection_confidence,
        )
        self._landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)

    def close(self) -> None:
        """Release underlying MediaPipe resources."""
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None

    def __enter__(self) -> ArmPoseClassifier:
        self.load()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def predict_rgb(self, rgb: np.ndarray) -> tuple[ArmPoseResult, list[Any]]:
        """Run PoseLandmarker on an RGB array and return `(ArmPoseResult, landmarks)`."""
        if self._landmarker is None:
            self.load()
        assert self._landmarker is not None
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        detection = self._landmarker.detect(mp_image)
        landmarks = detection.pose_landmarks[0] if detection.pose_landmarks else []
        return classify_pose_landmarks(landmarks, self.config), landmarks

    def predict_path(self, image_path: Path) -> tuple[ArmPoseResult, list[Any], np.ndarray]:
        """Load, validate, and classify an image path."""
        rgb = load_rgb_image(image_path, self.config)
        result, landmarks = self.predict_rgb(rgb)
        return result, landmarks, rgb
