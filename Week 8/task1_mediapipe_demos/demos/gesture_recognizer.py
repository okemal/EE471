"""MediaPipe Gesture Recognizer demo (canned hand gesture & handedness classification)."""

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
    """Recognize hand gestures and handedness on sample gesture photos."""
    resolved_model = ensure_model("gesture_recognizer", model_path=model_path)
    out_dir = output_dir(output_path)
    print_header("Gesture Recognizer", "vision", resolved_model)

    images = (
        [input_path]
        if input_path is not None
        else [ensure_sample_image("thumbs_up.jpg"), ensure_sample_image("victory.jpg")]
    )

    options = mp.tasks.vision.GestureRecognizerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_hands=2,
    )

    records: list[dict[str, object]] = []
    with mp.tasks.vision.GestureRecognizer.create_from_options(options) as recognizer:
        for img_path in images:
            rgb = load_rgb_image(img_path)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = recognizer.recognize(mp_image)
            gestures = [
                {
                    "gesture": g[0].category_name,
                    "score": round(float(g[0].score), 4),
                    "handedness": (
                        result.handedness[idx][0].category_name
                        if idx < len(result.handedness) and result.handedness[idx]
                        else "Unknown"
                    ),
                }
                for idx, g in enumerate(result.gestures)
                if g
            ]
            annotated = draw_landmark_points(
                rgb,
                result.hand_landmarks,
                connections=mp.tasks.vision.HandLandmarksConnections.HAND_CONNECTIONS,
                point_color=(245, 158, 11),
                line_color=(34, 197, 94),
                radius=4,
            )
            saved = save_rgb_image(annotated, out_dir / f"gesture_recognizer_{img_path.stem}.png")
            records.append(
                {"input": str(img_path), "gestures": gestures, "output_image": str(saved)}
            )
            print(f"{img_path.name}: {gestures} -> {saved}")

    return {"task": "gesture_recognizer", "model": resolved_model.name, "results": records}


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
