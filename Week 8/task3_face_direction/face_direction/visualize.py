"""Annotated face-direction visualization helper for Task 3 demonstrations."""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image

from face_direction.classifier import NOSE_TIP_IDX, FaceDirectionResult


def render_annotated_face(
    rgb: np.ndarray,
    landmarks: Sequence[Any],
    result: FaceDirectionResult,
) -> np.ndarray:
    """Draw face contour mesh, nose direction arrow, yaw angle, and classification badge."""
    canvas = rgb.copy()
    height, width = canvas.shape[:2]

    if landmarks:
        pts = [(int(lm.x * width), int(lm.y * height)) for lm in landmarks]
        for conn in mp.tasks.vision.FaceLandmarksConnections.FACE_LANDMARKS_CONTOURS:
            if conn.start < len(pts) and conn.end < len(pts):
                cv2.line(canvas, pts[conn.start], pts[conn.end], (148, 163, 184), 1, cv2.LINE_AA)

        if NOSE_TIP_IDX < len(pts):
            nose_x, nose_y = pts[NOSE_TIP_IDX]
            arrow_len = max(36, int(width * 0.22))
            if result.yaw_deg is not None:
                dx = int(arrow_len * math.sin(math.radians(result.yaw_deg)))
            else:
                dx = int(arrow_len * max(-1.0, min(1.0, result.asymmetry)))
            dy = (
                int(-arrow_len * 0.4 * math.sin(math.radians(result.pitch_deg)))
                if result.pitch_deg is not None
                else 0
            )
            cv2.circle(canvas, (nose_x, nose_y), 4, (239, 68, 68), -1, cv2.LINE_AA)
            cv2.arrowedLine(
                canvas,
                (nose_x, nose_y),
                (nose_x + dx, nose_y + dy),
                (34, 197, 94),
                3,
                cv2.LINE_AA,
                tipLength=0.28,
            )

    yaw_str = f" ({result.yaw_deg:+.1f} deg)" if result.yaw_deg is not None else ""
    banner = f"Looking: {result.direction}{yaw_str}"
    cv2.rectangle(canvas, (6, 6), (min(width - 6, 250), 34), (15, 23, 42), -1)
    cv2.putText(
        canvas,
        banner,
        (12, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (248, 250, 252),
        1,
        cv2.LINE_AA,
    )
    return canvas


def save_annotated_face(
    rgb: np.ndarray,
    landmarks: Sequence[Any],
    result: FaceDirectionResult,
    destination: Path,
) -> Path:
    """Render and write an annotated PNG visualization to `destination`."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = render_annotated_face(rgb, landmarks, result)
    Image.fromarray(rendered).save(destination)
    return destination
