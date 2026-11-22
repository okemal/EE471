"""MediaPipe Image Classifier demo (EfficientNet-Lite0 ImageNet-1K classification)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, print_header
from mediapipe_demos.models import ensure_model
from mediapipe_demos.samples import ensure_sample_image
from mediapipe_demos.visualize import load_rgb_image


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Classify sample images into top-5 ImageNet categories using EfficientNet-Lite0."""
    _ = output_path
    resolved_model = ensure_model("image_classifier", model_path=model_path)
    print_header("Image Classifier", "vision", resolved_model)

    images = (
        [input_path]
        if input_path is not None
        else [ensure_sample_image("burger.jpg"), ensure_sample_image("cat_and_dog.jpg")]
    )

    options = mp.tasks.vision.ImageClassifierOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        max_results=5,
    )

    records: list[dict[str, object]] = []
    with mp.tasks.vision.ImageClassifier.create_from_options(options) as classifier:
        for img_path in images:
            rgb = load_rgb_image(img_path)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = classifier.classify(mp_image)
            cats = [
                {"category": c.category_name, "score": round(float(c.score), 4)}
                for c in result.classifications[0].categories
            ]
            records.append({"input": str(img_path), "top_categories": cats})
            top_str = ", ".join(f"{c['category']} ({c['score']:.2f})" for c in cats[:3])
            print(f"{img_path.name}: {top_str}")

    return {"task": "image_classifier", "model": resolved_model.name, "results": records}


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
