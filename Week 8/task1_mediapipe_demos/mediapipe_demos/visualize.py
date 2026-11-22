"""Headless visualization helpers for Task 1 MediaPipe vision demos."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps


def load_rgb_image(path: Path) -> np.ndarray:
    """Load an image file into a contiguous uint8 RGB NumPy array with EXIF orientation applied."""
    with Image.open(path) as img:
        rgb = ImageOps.exif_transpose(img).convert("RGB")
        return np.ascontiguousarray(np.array(rgb, dtype=np.uint8))


def save_rgb_image(rgb: np.ndarray, destination: Path) -> Path:
    """Save an RGB uint8 NumPy array to disk as PNG."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.asarray(rgb, dtype=np.uint8)).save(destination)
    return destination


def draw_detections(rgb: np.ndarray, detections: list[Any]) -> np.ndarray:
    """Render bounding boxes, labels, and optional facial keypoints onto a copy of `rgb`."""
    canvas = rgb.copy()
    height, width = canvas.shape[:2]
    for det in detections:
        bbox = det.bounding_box
        x1, y1 = int(bbox.origin_x), int(bbox.origin_y)
        x2, y2 = x1 + int(bbox.width), y1 + int(bbox.height)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (34, 197, 94), 2)
        if det.categories:
            top = det.categories[0]
            label = f"{top.category_name or 'face'} {top.score:.2f}"
            cv2.rectangle(
                canvas, (x1, max(0, y1 - 22)), (min(width, x1 + 190), y1), (34, 197, 94), -1
            )
            cv2.putText(
                canvas,
                label,
                (x1 + 4, max(15, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (15, 23, 42),
                1,
                cv2.LINE_AA,
            )
        if getattr(det, "keypoints", None):
            for kp in det.keypoints:
                cx, cy = int(kp.x * width), int(kp.y * height)
                cv2.circle(canvas, (cx, cy), 4, (239, 68, 68), -1)
    return canvas


def draw_landmark_points(
    rgb: np.ndarray,
    landmark_lists: list[list[Any]],
    *,
    connections: Any = None,
    point_color: tuple[int, int, int] = (56, 189, 248),
    line_color: tuple[int, int, int] = (248, 250, 252),
    radius: int = 3,
) -> np.ndarray:
    """Draw normalized 2D landmarks and optional skeleton edges on a copy of `rgb`."""
    canvas = rgb.copy()
    height, width = canvas.shape[:2]
    for landmarks in landmark_lists:
        pts = [(int(lm.x * width), int(lm.y * height)) for lm in landmarks]
        if connections is not None:
            for conn in connections:
                start = getattr(conn, "start", conn[0] if isinstance(conn, tuple) else None)
                end = getattr(conn, "end", conn[1] if isinstance(conn, tuple) else None)
                if start is not None and end is not None and start < len(pts) and end < len(pts):
                    cv2.line(canvas, pts[start], pts[end], line_color, 2, cv2.LINE_AA)
        for px, py in pts:
            cv2.circle(canvas, (px, py), radius, point_color, -1, cv2.LINE_AA)
    return canvas


def colorize_category_mask(
    rgb: np.ndarray, category_mask: np.ndarray, alpha: float = 0.55
) -> np.ndarray:
    """Blend a per-pixel integer category mask onto `rgb` using a deterministic palette."""
    mask = np.squeeze(np.asarray(category_mask, dtype=np.int32))
    palette = np.array(
        [
            [15, 23, 42],
            [239, 68, 68],
            [34, 197, 94],
            [59, 130, 246],
            [245, 158, 11],
            [168, 85, 247],
            [20, 184, 166],
            [236, 72, 153],
            [132, 204, 22],
            [249, 115, 22],
            [14, 165, 233],
            [217, 70, 239],
            [234, 179, 8],
            [99, 102, 241],
            [16, 185, 129],
            [244, 63, 94],
            [6, 182, 212],
            [139, 92, 246],
            [251, 146, 60],
            [74, 222, 128],
            [96, 165, 250],
        ],
        dtype=np.uint8,
    )
    colored = palette[mask % len(palette)]
    if colored.shape[:2] != rgb.shape[:2]:
        colored = cv2.resize(colored, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST)
    fg = mask > 0
    if fg.shape[:2] != rgb.shape[:2]:
        fg = cv2.resize(
            fg.astype(np.uint8), (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST
        ).astype(bool)
    blended = rgb.astype(np.float32).copy()
    blended[fg] = (1.0 - alpha) * blended[fg] + alpha * colored[fg].astype(np.float32)
    return np.clip(blended, 0, 255).astype(np.uint8)


def overlay_binary_mask(
    rgb: np.ndarray,
    mask: np.ndarray,
    *,
    point_norm: tuple[float, float] | None = None,
    tint: tuple[int, int, int] = (56, 189, 248),
) -> np.ndarray:
    """Highlight a segmented foreground mask and optional user stroke point on `rgb`."""
    arr = np.squeeze(np.asarray(mask))
    fg = arr > 0.5 if np.issubdtype(arr.dtype, np.floating) else arr > 0
    if fg.shape[:2] != rgb.shape[:2]:
        fg = cv2.resize(
            fg.astype(np.uint8), (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST
        ).astype(bool)
    out = (rgb.astype(np.float32) * 0.35).astype(np.uint8)
    highlight = np.clip(
        rgb.astype(np.float32) * 0.7 + np.array(tint, dtype=np.float32) * 0.3, 0, 255
    ).astype(np.uint8)
    out[fg] = highlight[fg]
    if point_norm is not None:
        px = int(point_norm[0] * rgb.shape[1])
        py = int(point_norm[1] * rgb.shape[0])
        cv2.circle(out, (px, py), 9, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(out, (px, py), 6, (239, 68, 68), -1, cv2.LINE_AA)
    return out
