"""3D head-pose matrix, 2D landmark symmetry, and FaceLandmarker direction classifier."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import mediapipe as mp
import numpy as np

from face_direction.config import FaceDirectionConfig, load_rgb_image, settings, verify_model_file

DirectionLabel = Literal["left", "right", "straight"]

# Canonical MediaPipe 478-point FaceLandmarker indices used for symmetry cross-checking.
NOSE_TIP_IDX = 1
LEFT_FACE_EDGE_IDX = 234
RIGHT_FACE_EDGE_IDX = 454


class NoFaceDetectedError(ValueError):
    """Raised when FaceLandmarker finds zero faces in the input image."""


@dataclass(frozen=True)
class FaceDirectionResult:
    """Structured looking-direction prediction and geometric diagnostics."""

    direction: DirectionLabel
    signal_source: Literal["pose_matrix", "gaze_blendshapes", "landmark_asymmetry"]
    yaw_deg: float | None
    pitch_deg: float | None
    roll_deg: float | None
    asymmetry: float
    gaze_score: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize prediction and diagnostics to a JSON-compatible dictionary."""
        return asdict(self)


def extract_head_pose_degrees(transform_matrix: np.ndarray) -> tuple[float, float, float]:
    """Extract viewer-relative `(yaw_deg, pitch_deg, roll_deg)` from MediaPipe's 4x4 matrix.

    The upper-left 3x3 rotation block maps the canonical face +Z forward normal into camera space:
    - `yaw_deg < 0`: face points toward viewer's left (image-left)
    - `yaw_deg > 0`: face points toward viewer's right (image-right)
    - `yaw_deg ~ 0`: face points straight toward camera
    """
    mat = np.asarray(transform_matrix, dtype=np.float64)
    if mat.shape != (4, 4):
        raise ValueError(f"Expected 4x4 transformation matrix, got shape {mat.shape}")
    rot = mat[:3, :3]
    yaw = math.degrees(math.atan2(float(rot[0, 2]), float(rot[2, 2])))
    pitch = math.degrees(
        math.atan2(-float(rot[1, 2]), math.hypot(float(rot[0, 2]), float(rot[2, 2])))
    )
    roll = math.degrees(math.atan2(float(rot[1, 0]), float(rot[0, 0])))
    return yaw, pitch, roll


def compute_landmark_asymmetry(landmarks: Sequence[Any]) -> float:
    """Compute signed normalized horizontal offset of the nose tip between outer face edges."""
    if len(landmarks) <= RIGHT_FACE_EDGE_IDX:
        raise ValueError(f"Expected >= 455 face landmarks, got {len(landmarks)}")
    nose_x = float(landmarks[NOSE_TIP_IDX].x)
    left_x = float(landmarks[LEFT_FACE_EDGE_IDX].x)
    right_x = float(landmarks[RIGHT_FACE_EDGE_IDX].x)
    center_x = 0.5 * (left_x + right_x)
    span = max(abs(right_x - left_x), 1e-4)
    return (nose_x - center_x) / span


def compute_viewer_gaze_score(blendshapes: Sequence[Any] | None) -> float:
    """Compute signed viewer-relative horizontal eye-gaze score in [-1, 1].

    Negative indicates looking toward viewer's left; positive toward viewer's right.
    """
    if not blendshapes:
        return 0.0
    scores = {str(c.category_name): float(c.score) for c in blendshapes}
    look_left = 0.5 * (scores.get("eyeLookOutLeft", 0.0) + scores.get("eyeLookInRight", 0.0))
    look_right = 0.5 * (scores.get("eyeLookInLeft", 0.0) + scores.get("eyeLookOutRight", 0.0))
    return look_right - look_left


def classify_face_signals(
    landmarks: Sequence[Any],
    *,
    transform_matrix: np.ndarray | None = None,
    blendshapes: Sequence[Any] | None = None,
    config: FaceDirectionConfig = settings,
) -> FaceDirectionResult:
    """Classify viewer-relative looking direction (`'left'`, `'right'`, or `'straight'`)."""
    asymmetry = compute_landmark_asymmetry(landmarks)
    gaze_score = compute_viewer_gaze_score(blendshapes)

    yaw_deg: float | None = None
    pitch_deg: float | None = None
    roll_deg: float | None = None

    if transform_matrix is not None:
        yaw_deg, pitch_deg, roll_deg = extract_head_pose_degrees(transform_matrix)
        if yaw_deg <= -config.yaw_threshold_deg:
            direction: DirectionLabel = "left"
            source: Literal["pose_matrix", "gaze_blendshapes", "landmark_asymmetry"] = "pose_matrix"
        elif yaw_deg >= config.yaw_threshold_deg:
            direction = "right"
            source = "pose_matrix"
        elif abs(gaze_score) >= config.gaze_override_threshold:
            direction = "left" if gaze_score < 0 else "right"
            source = "gaze_blendshapes"
        else:
            direction = "straight"
            source = "pose_matrix"
    else:
        if asymmetry <= -config.asymmetry_threshold:
            direction = "left"
            source = "landmark_asymmetry"
        elif asymmetry >= config.asymmetry_threshold:
            direction = "right"
            source = "landmark_asymmetry"
        elif abs(gaze_score) >= config.gaze_override_threshold:
            direction = "left" if gaze_score < 0 else "right"
            source = "gaze_blendshapes"
        else:
            direction = "straight"
            source = "landmark_asymmetry"

    return FaceDirectionResult(
        direction=direction,
        signal_source=source,
        yaw_deg=round(yaw_deg, 2) if yaw_deg is not None else None,
        pitch_deg=round(pitch_deg, 2) if pitch_deg is not None else None,
        roll_deg=round(roll_deg, 2) if roll_deg is not None else None,
        asymmetry=round(asymmetry, 4),
        gaze_score=round(gaze_score, 4),
    )


class FaceDirectionClassifier:
    """Stateful MediaPipe FaceLandmarker inference engine for single-image gaze/head direction."""

    def __init__(self, config: FaceDirectionConfig = settings) -> None:
        self.config = config
        self._landmarker: mp.tasks.vision.FaceLandmarker | None = None

    def load(self) -> None:
        """Verify model SHA-256 and initialize MediaPipe FaceLandmarker on CPU."""
        if self._landmarker is not None:
            return
        model_file = verify_model_file(
            self.config.model_path,
            self.config.expected_sha256,
            verify_hash=self.config.verify_sha256,
        )
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=str(model_file),
                delegate=mp.tasks.BaseOptions.Delegate.CPU,
            ),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=self.config.min_face_detection_confidence,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)

    def close(self) -> None:
        """Release underlying MediaPipe resources."""
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None

    def __enter__(self) -> FaceDirectionClassifier:
        self.load()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def predict_rgb(self, rgb: np.ndarray) -> tuple[FaceDirectionResult, list[Any]]:
        """Run FaceLandmarker on an RGB array and return `(FaceDirectionResult, landmarks)`."""
        if self._landmarker is None:
            self.load()
        assert self._landmarker is not None
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        detection = self._landmarker.detect(mp_image)
        if not detection.face_landmarks:
            raise NoFaceDetectedError("No face detected in input image.")
        landmarks = detection.face_landmarks[0]
        matrix = (
            detection.facial_transformation_matrixes[0]
            if detection.facial_transformation_matrixes
            else None
        )
        blendshapes = detection.face_blendshapes[0] if detection.face_blendshapes else None
        result = classify_face_signals(
            landmarks,
            transform_matrix=matrix,
            blendshapes=blendshapes,
            config=self.config,
        )
        return result, landmarks

    def predict_path(self, image_path: Path) -> tuple[FaceDirectionResult, list[Any], np.ndarray]:
        """Load, validate, and classify the looking direction of the face in `image_path`."""
        rgb = load_rgb_image(image_path, self.config)
        result, landmarks = self.predict_rgb(rgb)
        return result, landmarks, rgb
