"""MediaPipe Text Proofreader demo (200M quantized on-device grammar & spelling correction)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, print_header
from mediapipe_demos.models import ensure_model

SAMPLE_INPUTS: list[str] = [
    "Their are severel typos in this sentance that needs fixing.",
    "Me and my team has build a containerize model with mediapipe yesterday.",
]


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Proofread sample sentences with grammatical and spelling mistakes on CPU."""
    _ = input_path, output_path
    resolved_model = ensure_model("text_proofreader", model_path=model_path)
    print_header("Text Proofreader", "text", resolved_model)

    cache_dir = Path(tempfile.gettempdir()) / "mediapipe_text_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    options = mp.tasks.text.TextProofreaderOptions(
        base_options=mp.tasks.BaseOptions(
            model_asset_path=str(resolved_model),
            delegate=mp.tasks.BaseOptions.Delegate.CPU,
        ),
        max_num_tokens=1024,
        cache_dir=str(cache_dir),
    )

    items: list[dict[str, object]] = []
    with mp.tasks.text.TextProofreader.create_from_options(options) as proofreader:
        for raw in SAMPLE_INPUTS:
            result = proofreader.proofread(raw)
            corrected = result.proofread_text.strip()
            corrections = [
                {"type": str(c.type), "text": c.text} for c in (result.corrections or [])
            ]
            items.append({"original": raw, "corrected": corrected, "corrections": corrections})
            print(f"Original:  {raw}")
            print(f"Corrected: {corrected}")
            print(f"Edits:     {len(corrections)} correction span(s)\n")

    return {"task": "text_proofreader", "model": resolved_model.name, "results": items}


def main() -> None:
    args = build_demo_parser(__doc__, supports_input=False).parse_args()
    run_demo(model_path=args.model, output_path=args.output_dir)


if __name__ == "__main__":
    main()
