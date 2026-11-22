"""CLI entrypoint for Task 2: classify which arm is raised in an input image.

Input:  $PATH-TO-INPUT-IMAGE
Output: "left", "right", "both", or "None" (subject anatomical perspective)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from arm_pose.classifier import ArmPoseClassifier
from arm_pose.config import InvalidImageError, settings
from arm_pose.visualize import save_annotated_pose


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for `classify_arm.py`."""
    parser = argparse.ArgumentParser(
        description=(
            "Detect body pose with MediaPipe PoseLandmarker and classify which arm is up "
            "('left', 'right', 'both', or 'None')."
        )
    )
    parser.add_argument("image", type=Path, help="Path to the input image ($PATH-TO-INPUT-IMAGE).")
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="Optional override path to pose_landmarker_full.task.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print structured JSON including normalized wrist/elbow metrics.",
    )
    parser.add_argument(
        "--annotate",
        type=Path,
        default=None,
        help="Optional PNG destination to save an annotated pose overlay.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run arm-pose classification and print the exact label (or JSON diagnostics)."""
    args = build_parser().parse_args(argv)
    config = (
        replace(settings, model_path=args.model, verify_sha256=False)
        if args.model is not None
        else settings
    )

    try:
        with ArmPoseClassifier(config) as classifier:
            result, landmarks, rgb = classifier.predict_path(args.image)
    except (InvalidImageError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.annotate is not None:
        save_annotated_pose(rgb, landmarks, result, args.annotate)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
