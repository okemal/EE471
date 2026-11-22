"""MediaPipe Text Embedder demo (Universal Sentence Encoder cosine similarity)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, print_header
from mediapipe_demos.models import ensure_model


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Embed sentences and contrast cosine similarity of semantically similar vs unrelated pairs."""
    _ = input_path, output_path
    resolved_model = ensure_model("text_embedder", model_path=model_path)
    print_header("Text Embedder", "text", resolved_model)

    options = mp.tasks.text.TextEmbedderOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
        l2_normalize=True,
    )

    anchor = "It was a charming and deeply moving journey across the mountains."
    similar = "What a wonderful and inspiring trip through the alpine peaks!"
    unrelated = "The Docker daemon failed to bind TCP port 5004 because it is already in use."

    with mp.tasks.text.TextEmbedder.create_from_options(options) as embedder:
        emb_anchor = embedder.embed(anchor).embeddings[0]
        emb_similar = embedder.embed(similar).embeddings[0]
        emb_unrelated = embedder.embed(unrelated).embeddings[0]

        sim_close = float(mp.tasks.text.TextEmbedder.cosine_similarity(emb_anchor, emb_similar))
        sim_far = float(mp.tasks.text.TextEmbedder.cosine_similarity(emb_anchor, emb_unrelated))

    dim = len(emb_anchor.embedding)
    print(f"Embedding dimension:    {dim}")
    print(f"Cosine(anchor, similar):   {sim_close:.4f}")
    print(f"Cosine(anchor, unrelated): {sim_far:.4f}")

    return {
        "task": "text_embedder",
        "model": resolved_model.name,
        "embedding_dim": dim,
        "similarity_similar": round(sim_close, 4),
        "similarity_unrelated": round(sim_far, 4),
    }


def main() -> None:
    args = build_demo_parser(__doc__, supports_input=False).parse_args()
    run_demo(model_path=args.model, output_path=args.output_dir)


if __name__ == "__main__":
    main()
