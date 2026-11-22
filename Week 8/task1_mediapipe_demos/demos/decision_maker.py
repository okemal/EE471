"""MediaPipe Decision Maker demo (EmbeddingGemma-2 270M choice & boolean routing)."""

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
    """Evaluate categorical choice routing, boolean safety checks, and batch decisions."""
    _ = input_path, output_path
    resolved_model = ensure_model("decision_maker", model_path=model_path)
    print_header("Decision Maker", "decision", resolved_model)

    options = mp.tasks.decision.DecisionMakerOptions(
        base_options=mp.tasks.BaseOptions(
            model_asset_path=str(resolved_model),
            delegate=mp.tasks.BaseOptions.Delegate.CPU,
        ),
        max_num_tokens=512,
    )

    routing_q = mp.tasks.decision.ChoiceQuestion(
        criteria={
            "billing": "Disputed charges, refund requests, invoice errors, or payment failures.",
            "technical": "App crashes, login errors, freeze, sync failures, or broken features.",
            "feature_request": (
                "Suggestions for new capabilities, UI enhancements, or integrations."
            ),
        },
        normalize_prior=True,
    )
    urgent_q = mp.tasks.decision.BooleanQuestion(
        condition="The user reports a critical outage or inability to access their account.",
        threshold=0.5,
        normalize_prior=True,
    )

    samples = [
        "The application crashes immediately after I enter my password.",
        "I was charged twice on my monthly invoice and need a refund.",
        "It would be helpful to add a dark mode toggle in settings.",
    ]

    decisions: list[dict[str, object]] = []
    with mp.tasks.decision.DecisionMaker.create_from_options(options) as maker:
        maker.prewarm(routing_q)
        for text in samples:
            choice = maker.evaluate_choice(text, routing_q)
            urgent = maker.evaluate_boolean(text, urgent_q)
            record = {
                "text": text,
                "selected": choice.selected_key,
                "confidence": round(float(choice.confidence), 4),
                "probabilities": {k: round(float(v), 4) for k, v in choice.probabilities.items()},
                "is_urgent": bool(urgent.value),
                "urgent_prob": round(float(urgent.probability_true), 4),
            }
            decisions.append(record)
            print(
                f"Input: '{text}'\n"
                f"  -> route={record['selected']} (conf={record['confidence']:.2f}) | "
                f"urgent={record['is_urgent']} ({record['urgent_prob']:.2f})"
            )

    return {"task": "decision_maker", "model": resolved_model.name, "decisions": decisions}


def main() -> None:
    args = build_demo_parser(__doc__, supports_input=False).parse_args()
    run_demo(model_path=args.model, output_path=args.output_dir)


if __name__ == "__main__":
    main()
