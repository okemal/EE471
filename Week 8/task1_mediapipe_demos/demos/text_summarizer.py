"""MediaPipe Text Summarizer demo (200M quantized 2-mode TLDR & Keypoints summarization)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, print_header
from mediapipe_demos.models import ensure_model

SAMPLE_ARTICLE = (
    "In modern software engineering, packaging machine learning models for reproducible "
    "deployment requires pinning Python dependencies, verifying model weights with cryptographic "
    "hashes, and isolating runtime environments inside containers. Tools like Docker and Cog "
    "standardize the inference interface by exposing a predictable HTTP prediction endpoint "
    "alongside command-line execution. Meanwhile, on-device frameworks such as MediaPipe Tasks "
    "compile vision, audio, text, retrieval, and decision models into compact quantized bundles "
    "that execute locally without round-tripping sensitive user media to remote cloud servers. "
    "Combining on-device inference with containerized packaging gives engineering teams both "
    "low-latency execution and deterministic cross-machine reproducibility."
)


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Summarize a technical paragraph in TLDR and KEYPOINTS modes."""
    _ = input_path, output_path
    resolved_model = ensure_model("text_summarizer", model_path=model_path)
    print_header("Text Summarizer", "text", resolved_model)

    cache_dir = Path(tempfile.gettempdir()) / "mediapipe_text_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    summaries: dict[str, str] = {}
    for label, mode in [
        ("tldr", mp.tasks.text.TextSummarizerMode.TLDR),
        ("keypoints", mp.tasks.text.TextSummarizerMode.KEYPOINTS),
    ]:
        options = mp.tasks.text.TextSummarizerOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=str(resolved_model),
                delegate=mp.tasks.BaseOptions.Delegate.CPU,
            ),
            mode=mode,
            max_num_tokens=1024,
            cache_dir=str(cache_dir),
        )
        with mp.tasks.text.TextSummarizer.create_from_options(options) as summarizer:
            result = summarizer.summarize(SAMPLE_ARTICLE)
            summaries[label] = result.summary.strip()
            print(f"[{label.upper()}]\n{summaries[label]}\n")

    return {
        "task": "text_summarizer",
        "model": resolved_model.name,
        "input_chars": len(SAMPLE_ARTICLE),
        "summaries": summaries,
    }


def main() -> None:
    args = build_demo_parser(__doc__, supports_input=False).parse_args()
    run_demo(model_path=args.model, output_path=args.output_dir)


if __name__ == "__main__":
    main()
