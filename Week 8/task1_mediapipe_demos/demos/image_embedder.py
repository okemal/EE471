"""MediaPipe Image Embedder demo (MobileNet-V3 Small visual cosine similarity)."""

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
    """Compare embeddings of an anchor image, a cropped variant, and an unrelated image."""
    _ = output_path
    resolved_model = ensure_model("image_embedder", model_path=model_path)
    print_header("Image Embedder", "vision", resolved_model)

    anchor_path = input_path if input_path is not None else ensure_sample_image("burger.jpg")
    similar_path = ensure_sample_image("burger_crop.jpg")
    different_path = ensure_sample_image("cat_and_dog.jpg")

    options = mp.tasks.vision.ImageEmbedderOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        l2_normalize=True,
        quantize=False,
    )

    with mp.tasks.vision.ImageEmbedder.create_from_options(options) as embedder:
        anchor_emb = embedder.embed(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=load_rgb_image(anchor_path))
        ).embeddings[0]
        similar_emb = embedder.embed(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=load_rgb_image(similar_path))
        ).embeddings[0]
        different_emb = embedder.embed(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=load_rgb_image(different_path))
        ).embeddings[0]

        sim_same = float(mp.tasks.vision.ImageEmbedder.cosine_similarity(anchor_emb, similar_emb))
        sim_diff = float(mp.tasks.vision.ImageEmbedder.cosine_similarity(anchor_emb, different_emb))

    dim = len(anchor_emb.embedding)
    print(f"Anchor: {anchor_path.name} (dim={dim})")
    print(f"Cosine({anchor_path.name}, {similar_path.name}):   {sim_same:.4f}")
    print(f"Cosine({anchor_path.name}, {different_path.name}): {sim_diff:.4f}")

    return {
        "task": "image_embedder",
        "model": resolved_model.name,
        "embedding_dim": dim,
        "similarity_similar": round(sim_same, 4),
        "similarity_different": round(sim_diff, 4),
    }


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
