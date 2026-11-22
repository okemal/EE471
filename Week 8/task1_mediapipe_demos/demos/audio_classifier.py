"""MediaPipe Audio Classifier demo (YAMNet 521-class sound event recognition)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, print_header
from mediapipe_demos.models import ensure_model
from mediapipe_demos.samples import (
    ensure_music_16k_wav,
    ensure_speech_16k_wav,
    read_wav_float32,
)


def _classify_clip(
    classifier: mp.tasks.audio.AudioClassifier, wav_path: Path
) -> list[dict[str, object]]:
    samples, sample_rate = read_wav_float32(wav_path)
    audio_data = mp.tasks.components.containers.AudioData.create_from_array(
        samples, sample_rate=sample_rate
    )
    results = classifier.classify(audio_data)
    windows: list[dict[str, object]] = []
    for window in results:
        if not window.classifications:
            continue
        top_categories = [
            {"category": cat.category_name, "score": round(float(cat.score), 4)}
            for cat in window.classifications[0].categories
        ]
        windows.append({"timestamp_ms": window.timestamp_ms, "categories": top_categories})
    return windows


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Run MediaPipe AudioClassifier on speech and musical audio clips."""
    _ = output_path
    resolved_model = ensure_model("audio_classifier", model_path=model_path)
    print_header("Audio Classifier", "audio", resolved_model)

    options = mp.tasks.audio.AudioClassifierOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
        running_mode=mp.tasks.audio.RunningMode.AUDIO_CLIPS,
        max_results=5,
    )

    clips = (
        [("custom", input_path)]
        if input_path is not None
        else [("speech", ensure_speech_16k_wav()), ("music", ensure_music_16k_wav())]
    )

    summary: dict[str, object] = {
        "task": "audio_classifier",
        "model": resolved_model.name,
        "clips": {},
    }
    with mp.tasks.audio.AudioClassifier.create_from_options(options) as classifier:
        for label, clip_path in clips:
            windows = _classify_clip(classifier, clip_path)
            summary["clips"][label] = {"file": str(clip_path), "windows": windows}
            top_line = (
                ", ".join(
                    f"{c['category']} ({c['score']:.2f})" for c in windows[0]["categories"][:3]
                )
                if windows
                else "no classifications"
            )
            print(f"[{label}] {clip_path.name}: {len(windows)} window(s) | top: {top_line}")

    return summary


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
