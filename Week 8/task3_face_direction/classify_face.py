"""CLI entrypoint for Task 3: classify face looking direction in an input image.

Input:  $PATH-TO-INPUT-IMAGE
Output: "left", "right", or "straight" (viewer-relative perspective)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from face_direction.classifier import FaceDirectionClassifier, NoFaceDetectedError
from face_direction.config import InvalidImageError, settings
from face_direction.visualize import save_annotated_face


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for `classify_face.py`."""
    parser = argparse.ArgumentParser(
        description=(
            "Detect face pose with MediaPipe FaceLandmarker and classify looking direction "
            "('left', 'right', or 'straight')."
        )
    )
    parser.add_argument("image", type=Path, help="Path to the input image ($PATH-TO-INPUT-IMAGE).")
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="Optional override path to face_landmarker.task.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print structured JSON including yaw/pitch/roll angles and asymmetry.",
    )
    parser.add_argument(
        "--annotate",
        type=Path,
        default=None,
        help="Optional PNG destination to save an annotated direction overlay.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run face-direction classification and print the exact label (or JSON diagnostics)."""
    args = build_parser().parse_args(argv)
    config = (
        replace(settings, model_path=args.model, verify_sha256=False)
        if args.model is not None
        else settings
    )

    try:
        with FaceDirectionClassifier(config) as classifier:
            result, landmarks, rgb = classifier.predict_path(args.image)
    except (InvalidImageError, NoFaceDetectedError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.annotate is not None:
        save_annotated_face(rgb, landmarks, result, args.annotate)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.direction)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
