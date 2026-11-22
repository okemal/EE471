"""MediaPipe Language Detector demo (110-language identification)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, print_header
from mediapipe_demos.models import ensure_model

SAMPLE_SENTENCES: list[tuple[str, str]] = [
    ("en", "Modern software engineering emphasizes reproducibility and automated testing."),
    ("tr", "İzmir Yüksek Teknoloji Enstitüsü modern yazılım geliştirme dersi."),
    ("fr", "Bonjour tout le monde, comment allez-vous aujourd'hui ?"),
    ("es", "El aprendizaje automático en el dispositivo protege la privacidad del usuario."),
    ("de", "Dieses Beispiel zeigt die Spracherkennung mit MediaPipe in Python."),
]


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Identify the language and confidence probability for multilingual sample sentences."""
    _ = input_path, output_path
    resolved_model = ensure_model("language_detector", model_path=model_path)
    print_header("Language Detector", "text", resolved_model)

    options = mp.tasks.text.LanguageDetectorOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
        score_threshold=0.1,
    )

    predictions: list[dict[str, object]] = []
    with mp.tasks.text.LanguageDetector.create_from_options(options) as detector:
        for expected, sentence in SAMPLE_SENTENCES:
            result = detector.detect(sentence)
            top = result.detections[0] if result.detections else None
            code = top.language_code if top else "unknown"
            prob = round(float(top.probability), 4) if top else 0.0
            predictions.append(
                {"expected": expected, "predicted": code, "probability": prob, "text": sentence}
            )
            print(f"[{expected} -> {code} ({prob:.3f})] {sentence}")

    return {"task": "language_detector", "model": resolved_model.name, "predictions": predictions}


def main() -> None:
    args = build_demo_parser(__doc__, supports_input=False).parse_args()
    run_demo(model_path=args.model, output_path=args.output_dir)


if __name__ == "__main__":
    main()
