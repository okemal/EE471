"""MediaPipe Image Segmenter demo (DeepLab-v3 21-class semantic segmentation)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp
import numpy as np

from mediapipe_demos.common import build_demo_parser, output_dir, print_header
from mediapipe_demos.models import ensure_model
from mediapipe_demos.samples import ensure_sample_image
from mediapipe_demos.visualize import colorize_category_mask, load_rgb_image, save_rgb_image


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Segment semantic object categories and save a colorized mask overlay PNG."""
    resolved_model = ensure_model("image_segmenter", model_path=model_path)
    image_path = input_path if input_path is not None else ensure_sample_image("cat_and_dog.jpg")
    out_dir = output_dir(output_path)
    print_header("Image Segmenter", "vision", resolved_model)

    rgb = load_rgb_image(image_path)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    options = mp.tasks.vision.ImageSegmenterOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        output_category_mask=True,
        output_confidence_masks=False,
    )
    with mp.tasks.vision.ImageSegmenter.create_from_options(options) as segmenter:
        labels = list(segmenter.labels)
        result = segmenter.segment(mp_image)
        mask = np.squeeze(result.category_mask.numpy_view()).copy()

    unique_ids, counts = np.unique(mask, return_counts=True)
    total_px = int(mask.size)
    class_shares = [
        {
            "id": int(cid),
            "label": labels[cid] if cid < len(labels) else f"class_{cid}",
            "coverage": round(float(cnt) / total_px, 4),
        }
        for cid, cnt in sorted(zip(unique_ids, counts, strict=True), key=lambda p: -p[1])
    ]

    overlay = colorize_category_mask(rgb, mask)
    saved = save_rgb_image(overlay, out_dir / "image_segmenter.png")
    print(f"Input:     {image_path.name} ({mask.shape[1]}x{mask.shape[0]})")
    print(f"Classes:   {class_shares[:5]}")
    print(f"Annotated: {saved}")

    return {
        "task": "image_segmenter",
        "model": resolved_model.name,
        "input": str(image_path),
        "classes": class_shares,
        "output_image": str(saved),
    }


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
