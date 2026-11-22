"""MediaPipe Semantic Retriever demo (on-device chunking, vector index & retrieval)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, print_header
from mediapipe_demos.models import ensure_model

DOCUMENTS: list[tuple[str, str, dict[str, str]]] = [
    (
        "doc_iztech",
        "Izmir Institute of Technology (IZTECH) is located in Urla, Izmir and hosts EE 471.",
        {"topic": "university"},
    ),
    (
        "doc_mediapipe",
        (
            "MediaPipe Tasks provides cross-platform on-device ML pipelines for "
            "vision, text, and audio."
        ),
        {"topic": "ml"},
    ),
    (
        "doc_cog",
        (
            "Cog packages Python machine learning models into reproducible Docker "
            "containers with HTTP APIs."
        ),
        {"topic": "containers"},
    ),
    (
        "doc_france",
        "The capital of France is Paris, famous for the Eiffel Tower and the Louvre Museum.",
        {"topic": "geography"},
    ),
]


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Index local documents with SemanticRetriever and run semantic top-k queries."""
    _ = input_path, output_path
    resolved_model = ensure_model("semantic_retriever", model_path=model_path)
    print_header("Semantic Retriever", "retrieval", resolved_model)

    cache_dir = Path(tempfile.gettempdir()) / "mediapipe_embedder_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    embedder_options = mp.tasks.retrieval.UniversalEmbedderOptions(
        base_options=mp.tasks.BaseOptions(
            model_asset_path=str(resolved_model),
            delegate=mp.tasks.BaseOptions.Delegate.CPU,
        ),
        l2_normalize=True,
        cache_dir=str(cache_dir),
    )

    queries = [
        "Which tool turns Python ML models into Docker containers?",
        "Where is Izmir Institute of Technology located?",
    ]

    query_results: list[dict[str, object]] = []
    with mp.tasks.retrieval.UniversalEmbedder.create_from_options(embedder_options) as embedder:
        retriever_options = mp.tasks.retrieval.SemanticRetrieverOptions(
            embedder=embedder,
            embedding_dimension=768,
            chunk_size=256,
            chunk_overlap=32,
            chunking_mode=mp.tasks.retrieval.ChunkingMode.CHARACTER,
        )
        with mp.tasks.retrieval.SemanticRetriever.create_from_options(
            retriever_options
        ) as retriever:
            for doc_id, text, meta in DOCUMENTS:
                retriever.insert_document(doc_id=doc_id, text=text, metadata=meta)

            for query in queries:
                hits = retriever.retrieve(query=query, limit=2, min_similarity=0.0)
                formatted = [
                    {
                        "id": h.id,
                        "score": round(float(h.score), 4),
                        "content": h.content,
                    }
                    for h in hits
                ]
                query_results.append({"query": query, "hits": formatted})
                print(f"Query: '{query}'")
                for rank, h in enumerate(formatted, start=1):
                    print(f"  #{rank} [{h['id']}] score={h['score']:.4f}: {h['content']}")

    return {
        "task": "semantic_retriever",
        "model": resolved_model.name,
        "indexed_docs": len(DOCUMENTS),
        "queries": query_results,
    }


def main() -> None:
    args = build_demo_parser(__doc__, supports_input=False).parse_args()
    run_demo(model_path=args.model, output_path=args.output_dir)


if __name__ == "__main__":
    main()
