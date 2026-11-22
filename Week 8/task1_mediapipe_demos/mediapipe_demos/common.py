"""Shared CLI and formatting helpers for Task 1 MediaPipe demonstrations."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "outputs"


def output_dir(override: Path | None = None) -> Path:
    """Return and create the directory where annotated visual/audio outputs are saved."""
    if override is not None:
        target = Path(override)
    else:
        env_dir = os.environ.get("MEDIAPIPE_DEMOS_OUTPUT_DIR")
        target = Path(env_dir) if env_dir else DEFAULT_OUTPUT_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def print_header(title: str, domain: str, model_path: Path) -> None:
    """Print a concise section header for terminal demos and screen recordings."""
    line = "=" * 72
    print(f"\n{line}")
    print(f"MediaPipe 1.2.3 Demo · {title} [{domain.upper()}]")
    print(f"Model: {model_path.name} ({model_path.stat().st_size / (1024 * 1024):.2f} MB)")
    print(line)


def build_demo_parser(description: str, *, supports_input: bool = True) -> argparse.ArgumentParser:
    """Create a consistent CLI parser shared by all 22 standalone demo scripts."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="Optional override path to a local .tflite / .task / .litertlm model file.",
    )
    if supports_input:
        parser.add_argument(
            "--input",
            type=Path,
            default=None,
            help="Optional override path to an input image or WAV audio file.",
        )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for generated visualizations or synthesized audio files.",
    )
    return parser
