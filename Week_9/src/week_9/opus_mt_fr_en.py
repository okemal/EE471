"""French-to-English neural machine translation demo using Helsinki-NLP/opus-mt-fr-en."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import torch
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    PreTrainedModel,
    PreTrainedTokenizerBase,
)

from week_9.config import configure_logging, get_hf_token, resolve_device

LOGGER = logging.getLogger(__name__)

MODEL_ID: Final[str] = "Helsinki-NLP/opus-mt-fr-en"
DEFAULT_TEXT: Final[str] = "Je voudrais un café, s'il vous plaît."
DEFAULT_MAX_NEW_TOKENS: Final[int] = 256


@dataclass(frozen=True, slots=True)
class TranslationResult:
    """Structured output returned by French-to-English translation.

    Attributes:
        model_id: Hugging Face model checkpoint identifier.
        device: Execution device string (for example, ``"cuda"`` or ``"cpu"``).
        source_text: Original French input text.
        translated_text: Translated English output text.
    """

    model_id: str
    device: str
    source_text: str
    translated_text: str


def load_model(
    *,
    model_id: str = MODEL_ID,
    device: str | None = None,
    token: str | None = None,
) -> tuple[PreTrainedTokenizerBase, PreTrainedModel, torch.device]:
    """Load the MarianMT tokenizer and seq2seq model onto the resolved device.

    Args:
        model_id: Hugging Face model repository ID or local directory.
        device: Optional device selector (``"auto"``, ``"cuda"``, ``"mps"``, ``"cpu"``).
        token: Optional Hugging Face access token. Defaults to ``HF_TOKEN`` from
            the environment or ``Week_9/.env``.

    Returns:
        Tuple of ``(tokenizer, model, resolved_device)``.
    """
    resolved_token = token if token is not None else get_hf_token()
    resolved_device = resolve_device(device)

    LOGGER.info("Loading %s on %s", model_id, resolved_device)
    tokenizer = AutoTokenizer.from_pretrained(model_id, token=resolved_token)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id, token=resolved_token)
    model.to(resolved_device)
    model.eval()
    if getattr(model, "generation_config", None) is not None:
        model.generation_config.max_length = None
    return tokenizer, model, resolved_device


def translate_text(
    text: str = DEFAULT_TEXT,
    *,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    model_id: str = MODEL_ID,
    device: str | None = None,
    token: str | None = None,
) -> TranslationResult:
    """Translate French ``text`` into English with OPUS-MT.

    Args:
        text: French source text to translate.
        max_new_tokens: Maximum number of generated target tokens (must be >= 1).
        model_id: Hugging Face model repository ID or local directory.
        device: Optional device selector (``"auto"``, ``"cuda"``, ``"mps"``, ``"cpu"``).
        token: Optional Hugging Face access token.

    Returns:
        A ``TranslationResult`` containing the translated English text.

    Raises:
        ValueError: If ``text`` is blank or ``max_new_tokens < 1``.
    """
    if not text.strip():
        raise ValueError("text must be a non-empty string.")
    if max_new_tokens < 1:
        raise ValueError("max_new_tokens must be at least 1.")

    tokenizer, model, resolved_device = load_model(
        model_id=model_id,
        device=device,
        token=token,
    )
    inputs = tokenizer(text, return_tensors="pt", truncation=True).to(resolved_device)

    with torch.inference_mode():
        outputs = model.generate(**inputs, max_new_tokens=max_new_tokens)

    translated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return TranslationResult(
        model_id=model_id,
        device=str(resolved_device),
        source_text=text,
        translated_text=translated_text,
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the French-to-English translation CLI."""
    parser = argparse.ArgumentParser(
        description="Translate French text to English with Helsinki-NLP/opus-mt-fr-en.",
    )
    parser.add_argument(
        "--text",
        default=DEFAULT_TEXT,
        help="French text to translate into English.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=DEFAULT_MAX_NEW_TOKENS,
        help="Maximum number of generated tokens (default: %(default)s).",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="PyTorch device override (auto, cuda, mps, cpu).",
    )
    parser.add_argument(
        "--model-id",
        default=MODEL_ID,
        help="Hugging Face checkpoint ID (default: %(default)s).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable informational logging.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the French-to-English translation CLI.

    Args:
        argv: Optional command-line argument sequence. Defaults to ``sys.argv[1:]``.

    Returns:
        Process exit status code (``0`` on success).
    """
    args = build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose)
    result = translate_text(
        text=args.text,
        max_new_tokens=args.max_new_tokens,
        model_id=args.model_id,
        device=args.device,
    )
    print(result.translated_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
