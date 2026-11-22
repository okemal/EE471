"""MediaPipe Holistic Landmarker demo (unified pose + face + left/right hands)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, output_dir, print_header
from mediapipe_demos.models import ensure_model
from mediapipe_demos.samples import input_photo
from mediapipe_demos.visualize import draw_landmark_points, load_rgb_image, save_rgb_image


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Detect unified body pose, face mesh, and hand landmarks in one forward pass."""
    resolved_model = ensure_model("holistic_landmarker", model_path=model_path)
    image_path = input_path if input_path is not None else input_photo("pose-2.jpg")
    out_dir = output_dir(output_path)
    print_header("Holistic Landmarker", "vision", resolved_model)

    rgb = load_rgb_image(image_path)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    options = mp.tasks.vision.HolisticLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        min_face_detection_confidence=0.3,
        min_pose_detection_confidence=0.5,
    )
    with mp.tasks.vision.HolisticLandmarker.create_from_options(options) as landmarker:
        result = landmarker.detect(mp_image)

    canvas = rgb.copy()
    if result.pose_landmarks:
        canvas = draw_landmark_points(
            canvas,
            [result.pose_landmarks],
            connections=mp.tasks.vision.PoseLandmarksConnections.POSE_LANDMARKS,
            point_color=(34, 197, 94),
            line_color=(248, 250, 252),
            radius=3,
        )
    if result.face_landmarks:
        canvas = draw_landmark_points(
            canvas,
            [result.face_landmarks],
            connections=mp.tasks.vision.FaceLandmarksConnections.FACE_LANDMARKS_CONTOURS,
            point_color=(56, 189, 248),
            line_color=(148, 163, 184),
            radius=1,
        )
    for hand_lms, color in [
        (result.left_hand_landmarks, (245, 158, 11)),
        (result.right_hand_landmarks, (239, 68, 68)),
    ]:
        if hand_lms:
            canvas = draw_landmark_points(
                canvas,
                [hand_lms],
                connections=mp.tasks.vision.HandLandmarksConnections.HAND_CONNECTIONS,
                point_color=color,
                line_color=color,
                radius=2,
            )

    saved = save_rgb_image(canvas, out_dir / "holistic_landmarker.png")
    counts = {
        "pose_landmarks": len(result.pose_landmarks),
        "face_landmarks": len(result.face_landmarks),
        "left_hand_landmarks": len(result.left_hand_landmarks),
        "right_hand_landmarks": len(result.right_hand_landmarks),
    }
    print(f"Input:     {image_path.name}")
    print(f"Counts:    {counts}")
    print(f"Annotated: {saved}")

    return {
        "task": "holistic_landmarker",
        "model": resolved_model.name,
        "input": str(image_path),
        "counts": counts,
        "output_image": str(saved),
    }


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
