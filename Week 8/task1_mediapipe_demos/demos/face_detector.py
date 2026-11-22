"""MediaPipe Face Detector demo (BlazeFace bounding boxes + 6 facial keypoints)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, output_dir, print_header
from mediapipe_demos.models import ensure_model
from mediapipe_demos.samples import input_photo
from mediapipe_demos.visualize import draw_detections, load_rgb_image, save_rgb_image


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Detect faces, bounding boxes, and 6 keypoints and save an annotated PNG."""
    resolved_model = ensure_model("face_detector", model_path=model_path)
    image_path = input_path if input_path is not None else input_photo("face-3.png")
    out_dir = output_dir(output_path)
    print_header("Face Detector", "vision", resolved_model)

    rgb = load_rgb_image(image_path)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    options = mp.tasks.vision.FaceDetectorOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        min_detection_confidence=0.5,
    )
    with mp.tasks.vision.FaceDetector.create_from_options(options) as detector:
        result = detector.detect(mp_image)

    annotated_path = save_rgb_image(
        draw_detections(rgb, result.detections), out_dir / "face_detector.png"
    )
    faces = [
        {
            "score": round(float(d.categories[0].score), 4) if d.categories else 0.0,
            "bbox": [
                d.bounding_box.origin_x,
                d.bounding_box.origin_y,
                d.bounding_box.width,
                d.bounding_box.height,
            ],
            "num_keypoints": len(d.keypoints),
        }
        for d in result.detections
    ]
    print(f"Input:     {image_path.name}")
    print(f"Detected:  {len(faces)} face(s) -> {faces}")
    print(f"Annotated: {annotated_path}")

    return {
        "task": "face_detector",
        "model": resolved_model.name,
        "input": str(image_path),
        "faces": faces,
        "output_image": str(annotated_path),
    }


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
