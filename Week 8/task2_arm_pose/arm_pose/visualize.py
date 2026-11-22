"""Annotated pose visualization helper for Task 2 demonstrations."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image

from arm_pose.classifier import (
    LEFT_ELBOW,
    LEFT_SHOULDER,
    LEFT_WRIST,
    RIGHT_ELBOW,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
    ArmPoseResult,
)


def render_annotated_pose(
    rgb: np.ndarray,
    landmarks: Sequence[Any],
    result: ArmPoseResult,
) -> np.ndarray:
    """Draw body skeleton, highlight raised arm segments, and overlay the classification verdict."""
    canvas = rgb.copy()
    height, width = canvas.shape[:2]

    if landmarks:
        pts = [(int(lm.x * width), int(lm.y * height)) for lm in landmarks]
        for conn in mp.tasks.vision.PoseLandmarksConnections.POSE_LANDMARKS:
            if conn.start < len(pts) and conn.end < len(pts):
                cv2.line(canvas, pts[conn.start], pts[conn.end], (226, 232, 240), 2, cv2.LINE_AA)

        # Highlight raised arm(s) in vivid green.
        if result.left and result.left.is_up:
            cv2.line(canvas, pts[LEFT_SHOULDER], pts[LEFT_ELBOW], (34, 197, 94), 5, cv2.LINE_AA)
            cv2.line(canvas, pts[LEFT_ELBOW], pts[LEFT_WRIST], (34, 197, 94), 5, cv2.LINE_AA)
        if result.right and result.right.is_up:
            cv2.line(canvas, pts[RIGHT_SHOULDER], pts[RIGHT_ELBOW], (34, 197, 94), 5, cv2.LINE_AA)
            cv2.line(canvas, pts[RIGHT_ELBOW], pts[RIGHT_WRIST], (34, 197, 94), 5, cv2.LINE_AA)

        for px, py in pts:
            cv2.circle(canvas, (px, py), 3, (56, 189, 248), -1, cv2.LINE_AA)

    banner = f"Arm up: {result.label}"
    cv2.rectangle(canvas, (8, 8), (min(width - 8, 220), 40), (15, 23, 42), -1)
    cv2.putText(
        canvas,
        banner,
        (16, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (248, 250, 252),
        2,
        cv2.LINE_AA,
    )
    return canvas


def save_annotated_pose(
    rgb: np.ndarray,
    landmarks: Sequence[Any],
    result: ArmPoseResult,
    destination: Path,
) -> Path:
    """Render and write an annotated PNG visualization to `destination`."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = render_annotated_pose(rgb, landmarks, result)
    Image.fromarray(rendered).save(destination)
    return destination
