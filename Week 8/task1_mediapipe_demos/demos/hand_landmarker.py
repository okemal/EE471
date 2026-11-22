"""MediaPipe Hand Landmarker demo (21 3D hand keypoints & handedness)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, output_dir, print_header
from mediapipe_demos.models import ensure_model
from mediapipe_demos.samples import ensure_sample_image
from mediapipe_demos.visualize import draw_landmark_points, load_rgb_image, save_rgb_image


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Detect 21 3D landmarks per hand and save an annotated visualization."""
    resolved_model = ensure_model("hand_landmarker", model_path=model_path)
    image_path = input_path if input_path is not None else ensure_sample_image("woman_hands.jpg")
    out_dir = output_dir(output_path)
    print_header("Hand Landmarker", "vision", resolved_model)

    rgb = load_rgb_image(image_path)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_hands=2,
    )
    with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker:
        result = landmarker.detect(mp_image)

    annotated = draw_landmark_points(
        rgb,
        result.hand_landmarks,
        connections=mp.tasks.vision.HandLandmarksConnections.HAND_CONNECTIONS,
        point_color=(56, 189, 248),
        line_color=(248, 250, 252),
        radius=4,
    )
    saved = save_rgb_image(annotated, out_dir / "hand_landmarker.png")
    hands = [
        {
            "handedness": result.handedness[idx][0].category_name,
            "score": round(float(result.handedness[idx][0].score), 4),
            "num_landmarks": len(lms),
        }
        for idx, lms in enumerate(result.hand_landmarks)
    ]
    print(f"Input:     {image_path.name}")
    print(f"Hands:     {hands}")
    print(f"Annotated: {saved}")

    return {
        "task": "hand_landmarker",
        "model": resolved_model.name,
        "input": str(image_path),
        "hands": hands,
        "output_image": str(saved),
    }


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
