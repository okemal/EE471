"""MediaPipe Text Classifier demo (MobileBERT sentiment analysis)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, print_header
from mediapipe_demos.models import ensure_model

SAMPLE_REVIEWS: list[str] = [
    "An unforgettable, brilliantly crafted film with superb performances!",
    "The plot dragged endlessly and the dialogue felt completely lifeless.",
    "Clean documentation, fast installation, and reliable test coverage.",
]


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Classify sentiment polarity on sample English text strings with MobileBERT."""
    _ = input_path, output_path
    resolved_model = ensure_model("text_classifier", model_path=model_path)
    print_header("Text Classifier", "text", resolved_model)

    options = mp.tasks.text.TextClassifierOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model))
    )

    records: list[dict[str, object]] = []
    with mp.tasks.text.TextClassifier.create_from_options(options) as classifier:
        for text in SAMPLE_REVIEWS:
            result = classifier.classify(text)
            cats = [
                {"category": c.category_name, "score": round(float(c.score), 4)}
                for c in result.classifications[0].categories
            ]
            records.append({"text": text, "categories": cats})
            top = cats[0]
            print(f"[{top['category']:>8} {top['score']:.3f}] {text}")

    return {"task": "text_classifier", "model": resolved_model.name, "predictions": records}


def main() -> None:
    args = build_demo_parser(__doc__, supports_input=False).parse_args()
    run_demo(model_path=args.model, output_path=args.output_dir)


if __name__ == "__main__":
    main()
