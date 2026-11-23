"""Unified CLI dispatcher for the Week 9 Hugging Face model demos."""

from __future__ import annotations

import argparse
import importlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ModelEntry:
    """Metadata describing an announced Week 9 model script.

    Attributes:
        command: CLI subcommand name.
        module: Dotted Python module path under ``week_9``.
        model_id: Default Hugging Face Hub repository ID.
        task: Short human-readable task label.
    """

    command: str
    module: str
    model_id: str
    task: str


MODEL_REGISTRY: Final[dict[str, ModelEntry]] = {
    "smollm2": ModelEntry(
        command="smollm2",
        module="week_9.smollm2",
        model_id="HuggingFaceTB/SmolLM2-360M",
        task="Causal text generation",
    ),
    "opus-mt-fr-en": ModelEntry(
        command="opus-mt-fr-en",
        module="week_9.opus_mt_fr_en",
        model_id="Helsinki-NLP/opus-mt-fr-en",
        task="French-to-English machine translation",
    ),
    "vit": ModelEntry(
        command="vit",
        module="week_9.vit",
        model_id="google/vit-base-patch16-224",
        task="ImageNet-1K image classification",
    ),
    "whisper": ModelEntry(
        command="whisper",
        module="week_9.whisper",
        model_id="openai/whisper-large-v3",
        task="Automatic speech recognition",
    ),
}


def format_model_list() -> str:
    """Render a concise summary table of the announced Week 9 models."""
    lines = ["Available Week 9 models:"]
    for entry in MODEL_REGISTRY.values():
        lines.append(f"  - {entry.command:<14} {entry.model_id:<32} ({entry.task})")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level ``week-9`` CLI parser."""
    parser = argparse.ArgumentParser(
        prog="week-9",
        description="Run EE471 Week 9 Hugging Face model demonstrations.",
    )
    parser.add_argument(
        "command",
        choices=("list", *MODEL_REGISTRY.keys()),
        help="Subcommand to execute ('list' or a model name).",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to the selected model CLI (use --help after the model name).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch the top-level ``week-9`` CLI command.

    Args:
        argv: Optional command-line argument sequence. Defaults to ``sys.argv[1:]``.

    Returns:
        Exit status code returned by the selected subcommand.
    """
    parsed = build_parser().parse_args(argv)
    if parsed.command == "list":
        print(format_model_list())
        return 0

    entry = MODEL_REGISTRY[parsed.command]
    module = importlib.import_module(entry.module)
    forwarded = list(parsed.args)
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]
    return int(module.main(forwarded))


if __name__ == "__main__":
    raise SystemExit(main())
