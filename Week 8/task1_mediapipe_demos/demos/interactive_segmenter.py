"""MediaPipe Interactive Segmenter demo (MagicTouch stroke-guided object cutout)."""

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
from mediapipe_demos.visualize import load_rgb_image, overlay_binary_mask, save_rgb_image


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Segment the object at a positive user click point using MediaPipe 1.2.3 Stroke API."""
    resolved_model = ensure_model("interactive_segmenter", model_path=model_path)
    image_path = input_path if input_path is not None else ensure_sample_image("cat_and_dog.jpg")
    out_dir = output_dir(output_path)
    print_header("Interactive Segmenter", "vision", resolved_model)

    rgb = load_rgb_image(image_path)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    options = mp.tasks.vision.InteractiveSegmenterOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model))
    )
    click_x, click_y = 0.65, 0.55  # lands cleanly on the dog in cat_and_dog.jpg
    stroke = mp.tasks.vision.InteractiveSegmenterStroke(
        brush_mode=mp.tasks.vision.InteractiveSegmenterBrushMode.POSITIVE,
        points=[mp.tasks.vision.InteractiveSegmenterStrokePoint(x=click_x, y=click_y)],
        is_completed=True,
    )

    with mp.tasks.vision.InteractiveSegmenter.create_from_options(options) as segmenter:
        segmenter.set_image(mp_image)
        mask_img = segmenter.segment([stroke])
        mask = np.squeeze(mask_img.numpy_view()).copy()

    fg_mask = mask > 0.5 if np.issubdtype(mask.dtype, np.floating) else mask > 0
    fg_ratio = round(float(np.mean(fg_mask)), 4)
    overlay = overlay_binary_mask(rgb, mask, point_norm=(click_x, click_y))
    saved = save_rgb_image(overlay, out_dir / "interactive_segmenter.png")
    print(f"Input:      {image_path.name} (click=({click_x:.2f}, {click_y:.2f}))")
    print(f"Foreground: {fg_ratio * 100:.1f}% of pixels segmented")
    print(f"Annotated:  {saved}")

    return {
        "task": "interactive_segmenter",
        "model": resolved_model.name,
        "input": str(image_path),
        "click_point": [click_x, click_y],
        "foreground_ratio": fg_ratio,
        "output_image": str(saved),
    }


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
