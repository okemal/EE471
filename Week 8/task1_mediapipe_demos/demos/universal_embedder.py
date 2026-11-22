"""MediaPipe Universal Embedder demo (multimodal text + image shared vector space)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, print_header
from mediapipe_demos.models import ensure_model
from mediapipe_demos.samples import ensure_sample_image


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Compute text, image, and composite embeddings and compare cross-modal cosine similarity."""
    _ = output_path
    resolved_model = ensure_model("universal_embedder", model_path=model_path)
    image_path = input_path if input_path is not None else ensure_sample_image("cat_and_dog.jpg")
    print_header("Universal Embedder", "retrieval", resolved_model)

    cache_dir = Path(tempfile.gettempdir()) / "mediapipe_embedder_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    options = mp.tasks.retrieval.UniversalEmbedderOptions(
        base_options=mp.tasks.BaseOptions(
            model_asset_path=str(resolved_model),
            delegate=mp.tasks.BaseOptions.Delegate.CPU,
        ),
        l2_normalize=True,
        cache_dir=str(cache_dir),
    )

    image_bytes = image_path.read_bytes()
    matching_caption = "A photo of a cat and a dog sitting together"
    unrelated_caption = "A commercial airplane flying above snowy mountains"

    with mp.tasks.retrieval.UniversalEmbedder.create_from_options(options) as embedder:
        img_emb = embedder.embed_image(image_bytes).embeddings[0]
        match_emb = embedder.embed_text(matching_caption).embeddings[0]
        unrelated_emb = embedder.embed_text(unrelated_caption).embeddings[0]
        composite_emb = embedder.embed_content(
            [
                mp.tasks.retrieval.TextPart(text=matching_caption),
                mp.tasks.retrieval.ImagePart(image_bytes=image_bytes),
            ]
        ).embeddings[0]

        sim_match = float(
            mp.tasks.retrieval.UniversalEmbedder.cosine_similarity(img_emb, match_emb)
        )
        sim_unrelated = float(
            mp.tasks.retrieval.UniversalEmbedder.cosine_similarity(img_emb, unrelated_emb)
        )
        sim_composite = float(
            mp.tasks.retrieval.UniversalEmbedder.cosine_similarity(composite_emb, match_emb)
        )

    dim = len(img_emb.embedding)
    print(f"Image:                 {image_path.name} (embedding dim={dim})")
    print(f"Cosine(image, match):  {sim_match:.4f}  ('{matching_caption}')")
    print(f"Cosine(image, other):  {sim_unrelated:.4f}  ('{unrelated_caption}')")
    print(f"Cosine(combo, match):  {sim_composite:.4f}")

    return {
        "task": "universal_embedder",
        "model": resolved_model.name,
        "image": str(image_path),
        "embedding_dim": dim,
        "similarity_match": round(sim_match, 4),
        "similarity_unrelated": round(sim_unrelated, 4),
        "similarity_composite": round(sim_composite, 4),
    }


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
