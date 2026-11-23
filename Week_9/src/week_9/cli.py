"""Unified CLI dispatcher for the Week 9 Hugging Face model and assignment demos."""

from __future__ import annotations

import argparse
import importlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from week_9.config import configure_logging
from week_9.task4 import (
    demonstrate_encode_and_decode,
    demonstrate_load_and_save,
    demonstrate_padding,
    demonstrate_special_tokens,
    demonstrate_truncation,
)
from week_9.tasks import Week9Tasks


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

TASK1_CHOICES: Final[tuple[str, ...]] = (
    "sentiment",
    "zero-shot",
    "generate",
    "fill-mask",
    "ner",
    "qa",
    "summarize",
    "translate",
    "image",
    "asr",
    "all",
)

TASK4_CHOICES: Final[tuple[str, ...]] = (
    "load-save",
    "encode-decode",
    "pad",
    "truncate",
    "special-tokens",
    "all",
)


def format_model_list() -> str:
    """Render a concise summary table of the announced Week 9 models and commands."""
    lines = ["Available Week 9 legacy model commands:"]
    for entry in MODEL_REGISTRY.values():
        lines.append(f"  - {entry.command:<14} {entry.model_id:<32} ({entry.task})")
    lines.extend(
        [
            "",
            "Assignment subcommands:",
            f"  - task1 <name>   ({', '.join(TASK1_CHOICES)})",
            f"  - task4 <name>   ({', '.join(TASK4_CHOICES)})",
            "  - app            Launch the 10-tab Gradio demo (default: 127.0.0.1:7860)",
        ]
    )
    return "\n".join(lines)


def _run_single_task1(runner: Week9Tasks, name: str) -> None:
    if name == "sentiment":
        res = runner.analyze_sentiment()
        print(f"=== Task 1: Sentiment Analysis ({res.model_id} on {res.device}) ===")
        for idx, item in enumerate(res.items, start=1):
            print(f"  {idx}. [{item.label} | {item.score:.4f}] {item.text}")
    elif name == "zero-shot":
        res = runner.classify_zero_shot()
        print(f"=== Task 1: Zero-Shot Classification ({res.model_id} on {res.device}) ===")
        print(f"  Text: {res.text}")
        for rank, item in enumerate(res.labels, start=1):
            print(f"  {rank}. {item.label:<12} {item.score:.4f}")
    elif name == "generate":
        res = runner.complete_text()
        print(f"=== Task 1: Text Generation ({res.model_id} on {res.device}) ===")
        print(f"  Prompt ({len(res.prompt.split())} words): {res.prompt}")
        for idx, comp in enumerate(res.completions, start=1):
            print(f"  {idx}. ({comp.word_count}/{res.max_words} words) {comp.text}")
    elif name == "fill-mask":
        res = runner.fill_mask()
        print(f"=== Task 1: Mask Filling ({res.model_id} on {res.device}) ===")
        print(f"  Input: {res.text}")
        for rank, cand in enumerate(res.candidates, start=1):
            print(f"  {rank}. {cand.token_str!r:<14} ({cand.score:.4f}) -> {cand.sequence}")
    elif name == "ner":
        res = runner.recognize_entities()
        print(f"=== Task 1: Named Entity Recognition ({res.model_id} on {res.device}) ===")
        print(f"  Text: {res.text}")
        for ent in res.entities:
            print(
                f"  - [{ent.entity_group}] {ent.text!r} "
                f"(chars {ent.start}:{ent.end}, score {ent.score:.4f})"
            )
    elif name == "qa":
        res = runner.answer_question()
        print(
            f"=== Task 1: Question Answering & NER Validation "
            f"({res.model_id} vs {res.ner_model_id} on {res.device}) ==="
        )
        print(f"  Context: {res.context}")
        for idx, item in enumerate(res.items, start=1):
            status = "AGREED" if item.agreed else "DISAGREED"
            print(f"  {idx}. Q: {item.question}")
            print(
                f"     QA: {item.answer!r} (score {item.score:.4f}) | "
                f"NER ({item.ner_group}): {item.ner_entity!r} -> {status}"
            )
    elif name == "summarize":
        res = runner.summarize()
        print(f"=== Task 1: Summarization ({res.model_id} on {res.device}) ===")
        print(f"  Source ({len(res.source_text.split())} words): {res.source_text}")
        print(f"  Summary ({len(res.summary_text.split())} words): {res.summary_text}")
    elif name == "translate":
        res = runner.translate_text()
        print(f"=== Task 1: French-to-English Translation ({res.model_id} on {res.device}) ===")
        print(f"  French : {res.source_text}")
        print(f"  English: {res.translated_text}")
    elif name == "image":
        res = runner.classify_image()
        print(f"=== Task 1: Image Classification ({res.model_id} on {res.device}) ===")
        print(f"  Image: {res.source}")
        for rank, pred in enumerate(res.predictions, start=1):
            print(f"  {rank}. {pred.label}: {pred.probability:.2%}")
    elif name == "asr":
        res = runner.transcribe_audio()
        print(f"=== Task 1: Automatic Speech Recognition ({res.model_id} on {res.device}) ===")
        print(f"  Audio: {res.source}")
        print(f"  Transcript: {res.text}")
        for chunk in res.chunks:
            start = f"{chunk.start_s:5.2f}s" if chunk.start_s is not None else " ?.??s"
            end = f"{chunk.end_s:5.2f}s" if chunk.end_s is not None else " ?.??s"
            print(f"  [{start} -> {end}] {chunk.text}")


def run_task1_cli(argv: Sequence[str]) -> int:
    """Run one or all Task 1 demonstrations."""
    parser = argparse.ArgumentParser(prog="week-9 task1", description="Run Week 9 Task 1 demos.")
    parser.add_argument("name", choices=TASK1_CHOICES, help="Task 1 demo name or 'all'.")
    parser.add_argument("--device", default=None, help="PyTorch device override.")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable informational logging."
    )
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)

    runner = Week9Tasks(device=args.device)
    targets = [n for n in TASK1_CHOICES if n != "all"] if args.name == "all" else [args.name]
    for idx, target in enumerate(targets):
        if idx > 0:
            print()
        _run_single_task1(runner, target)
    return 0


def _run_single_task4(name: str, *, device: str | None) -> None:
    if name == "load-save":
        res = demonstrate_load_and_save(device=device)
        print(f"=== Task 4.1: Load & Save ({res.model_id}) ===")
        print(f"  Saved files ({len(res.saved_files)}): {', '.join(res.saved_files)}")
        print(f"  Prompt: {res.prompt}")
        print(f"  Before save: {res.before_token!r} ({res.before_score:.4f})")
        print(f"  After local reload: {res.after_token!r} ({res.after_score:.4f})")
        print(f"  Predictions match: {res.predictions_match}")
    elif name == "encode-decode":
        res = demonstrate_encode_and_decode()
        print(f"=== Task 4.2: Encode & Decode ({res.model_id}) ===")
        print(f"  Original: {res.original_text}")
        print(f"  Pieces  : {list(res.tokens)}")
        print(f"  IDs     : {list(res.input_ids)}")
        print(f"  Decoded (special): {res.decoded_with_special}")
        print(f"  Decoded (clean)  : {res.decoded_without_special}")
        print(f"  Note: {res.explanation}")
    elif name == "pad":
        res = demonstrate_padding()
        print(f"=== Task 4.3: Input Padding ({res.model_id}) ===")
        print(f"  Pad token: {res.pad_token!r} (ID {res.pad_token_id})")
        for idx, (sent, ids, mask) in enumerate(
            zip(res.sentences, res.input_ids, res.attention_masks, strict=True)
        ):
            print(f"  Row {idx}: {sent!r}")
            print(f"    input_ids     : {list(ids)}")
            print(f"    attention_mask: {list(mask)}")
        print(
            f"  Shorter row ({res.shorter_row_index}) pad positions (ID={res.pad_token_id}, "
            f"mask=0): {list(res.pad_positions)}"
        )
    elif name == "truncate":
        res = demonstrate_truncation()
        print(f"=== Task 4.4: Input Truncation ({res.model_id}) ===")
        print(f"  Full length     : {res.full_length} tokens")
        print(
            f"  Truncated length: {res.truncated_length} tokens (max_length={res.max_length}, "
            f"dropped {res.dropped_tokens})"
        )
        print(f"  Retained tokens : {list(res.retained_tokens)}")
        print(f"  Decoded slice   : {res.truncated_text}")
    elif name == "special-tokens":
        res = demonstrate_special_tokens()
        print(f"=== Task 4.5: Adding Special Tokens ({res.model_id}) ===")
        print(f"  Sample text  : {res.sample_text}")
        print(f"  Tokens before: {list(res.tokens_before)}")
        print(f"  Tokens after : {list(res.tokens_after)}")
        print(f"  Added token  : {res.special_token!r} -> ID {res.special_token_id}")
        print(
            f"  Vocab size   : {res.vocab_size_before} -> {res.vocab_size_after} | "
            f"Embedding rows: {res.embedding_rows_before} -> {res.embedding_rows_after}"
        )


def run_task4_cli(argv: Sequence[str]) -> int:
    """Run one or all Task 4 Chapter 2 demonstrations."""
    parser = argparse.ArgumentParser(prog="week-9 task4", description="Run Week 9 Task 4 demos.")
    parser.add_argument("name", choices=TASK4_CHOICES, help="Task 4 demo name or 'all'.")
    parser.add_argument("--device", default=None, help="PyTorch device override.")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable informational logging."
    )
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)

    targets = [n for n in TASK4_CHOICES if n != "all"] if args.name == "all" else [args.name]
    for idx, target in enumerate(targets):
        if idx > 0:
            print()
        _run_single_task4(target, device=args.device)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level ``week-9`` CLI parser."""
    parser = argparse.ArgumentParser(
        prog="week-9",
        description="Run EE471 Week 9 Hugging Face model demonstrations.",
    )
    parser.add_argument(
        "command",
        choices=("list", "task1", "task4", "app", *MODEL_REGISTRY.keys()),
        help="Subcommand to execute.",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to the selected subcommand.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch the top-level ``week-9`` CLI command."""
    parsed = build_parser().parse_args(argv)
    forwarded = list(parsed.args)
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]

    if parsed.command == "list":
        print(format_model_list())
        return 0
    if parsed.command == "task1":
        return run_task1_cli(forwarded)
    if parsed.command == "task4":
        return run_task4_cli(forwarded)
    if parsed.command == "app":
        app_module = importlib.import_module("week_9.app")
        return int(app_module.main(forwarded))

    entry = MODEL_REGISTRY[parsed.command]
    module = importlib.import_module(entry.module)
    return int(module.main(forwarded))


if __name__ == "__main__":
    raise SystemExit(main())
