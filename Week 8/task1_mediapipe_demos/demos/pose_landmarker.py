"""MediaPipe Pose Landmarker demo (33 full-body 3D landmarks on pose-1..3.jpg)."""

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
    """Detect 33 body landmarks on the Week 8 pose images and save skeleton overlays."""
    resolved_model = ensure_model("pose_landmarker", model_path=model_path)
    out_dir = output_dir(output_path)
    print_header("Pose Landmarker", "vision", resolved_model)

    images = (
        [input_path]
        if input_path is not None
        else [input_photo("pose-1.jpg"), input_photo("pose-2.jpg"), input_photo("pose-3.jpg")]
    )

    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_poses=1,
    )

    records: list[dict[str, object]] = []
    with mp.tasks.vision.PoseLandmarker.create_from_options(options) as landmarker:
        for img_path in images:
            rgb = load_rgb_image(img_path)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(mp_image)
            annotated = draw_landmark_points(
                rgb,
                result.pose_landmarks,
                connections=mp.tasks.vision.PoseLandmarksConnections.POSE_LANDMARKS,
                point_color=(34, 197, 94),
                line_color=(248, 250, 252),
                radius=4,
            )
            saved = save_rgb_image(annotated, out_dir / f"pose_landmarker_{img_path.stem}.png")
            count = len(result.pose_landmarks[0]) if result.pose_landmarks else 0
            records.append(
                {
                    "input": str(img_path),
                    "num_poses": len(result.pose_landmarks),
                    "num_landmarks": count,
                    "output_image": str(saved),
                }
            )
            print(
                f"{img_path.name}: {len(result.pose_landmarks)} pose ({count} landmarks) -> {saved}"
            )

    return {"task": "pose_landmarker", "model": resolved_model.name, "results": records}


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
