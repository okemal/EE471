"""MediaPipe Object Detector demo (EfficientDet-Lite0 COCO bounding boxes)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, output_dir, print_header
from mediapipe_demos.models import ensure_model
from mediapipe_demos.samples import ensure_sample_image
from mediapipe_demos.visualize import draw_detections, load_rgb_image, save_rgb_image


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Detect labeled bounding boxes in a multi-object image and save an annotated PNG."""
    resolved_model = ensure_model("object_detector", model_path=model_path)
    image_path = input_path if input_path is not None else ensure_sample_image("cat_and_dog.jpg")
    out_dir = output_dir(output_path)
    print_header("Object Detector", "vision", resolved_model)

    rgb = load_rgb_image(image_path)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    options = mp.tasks.vision.ObjectDetectorOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        score_threshold=0.4,
        max_results=5,
    )
    with mp.tasks.vision.ObjectDetector.create_from_options(options) as detector:
        result = detector.detect(mp_image)

    saved = save_rgb_image(draw_detections(rgb, result.detections), out_dir / "object_detector.png")
    objects = [
        {
            "category": d.categories[0].category_name if d.categories else "unknown",
            "score": round(float(d.categories[0].score), 4) if d.categories else 0.0,
            "bbox": [
                d.bounding_box.origin_x,
                d.bounding_box.origin_y,
                d.bounding_box.width,
                d.bounding_box.height,
            ],
        }
        for d in result.detections
    ]
    print(f"Input:     {image_path.name}")
    print(f"Objects:   {objects}")
    print(f"Annotated: {saved}")

    return {
        "task": "object_detector",
        "model": resolved_model.name,
        "input": str(image_path),
        "detections": objects,
        "output_image": str(saved),
    }


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
