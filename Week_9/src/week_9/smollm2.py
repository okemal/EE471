"""Causal language model text generation demo using HuggingFaceTB/SmolLM2-360M."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    PreTrainedModel,
    PreTrainedTokenizerBase,
)

from week_9.config import configure_logging, get_hf_token, resolve_device, resolve_dtype

LOGGER = logging.getLogger(__name__)

MODEL_ID: Final[str] = "HuggingFaceTB/SmolLM2-360M"
DEFAULT_PROMPT: Final[str] = "Let's learn about the C programming language"
DEFAULT_MAX_NEW_TOKENS: Final[int] = 256


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Structured output returned by SmolLM2 text generation.

    Attributes:
        model_id: Hugging Face model checkpoint identifier.
        device: Execution device string (for example, ``"cuda"`` or ``"cpu"``).
        dtype: Floating-point precision used for model weights.
        prompt: Original input prompt string.
        generated_text: Decoded text including the prompt and completion.
        input_token_count: Number of tokens in the encoded prompt.
        generated_token_count: Number of newly generated tokens.
    """

    model_id: str
    device: str
    dtype: str
    prompt: str
    generated_text: str
    input_token_count: int
    generated_token_count: int


def load_model(
    *,
    model_id: str = MODEL_ID,
    device: str | None = None,
    token: str | None = None,
) -> tuple[PreTrainedTokenizerBase, PreTrainedModel, torch.device, torch.dtype]:
    """Load the SmolLM2 tokenizer and causal LM onto the resolved device.

    Args:
        model_id: Hugging Face model repository ID or local directory.
        device: Optional device selector (``"auto"``, ``"cuda"``, ``"mps"``, ``"cpu"``).
        token: Optional Hugging Face access token. Defaults to ``HF_TOKEN`` from
            the environment or ``Week_9/.env``.

    Returns:
        Tuple of ``(tokenizer, model, resolved_device, dtype)``.
    """
    resolved_token = token if token is not None else get_hf_token()
    resolved_device = resolve_device(device)
    dtype = resolve_dtype(resolved_device, prefer_bfloat16=True)

    LOGGER.info("Loading %s on %s (%s)", model_id, resolved_device, dtype)
    tokenizer = AutoTokenizer.from_pretrained(model_id, token=resolved_token)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        dtype=dtype,
        token=resolved_token,
    )
    model.to(resolved_device)
    model.eval()
    return tokenizer, model, resolved_device, dtype


def generate_text(
    prompt: str = DEFAULT_PROMPT,
    *,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    do_sample: bool = False,
    temperature: float | None = None,
    model_id: str = MODEL_ID,
    device: str | None = None,
    token: str | None = None,
) -> GenerationResult:
    """Generate a text continuation from ``prompt`` with SmolLM2-360M.

    Args:
        prompt: Input text prompt to continue.
        max_new_tokens: Maximum number of new tokens to generate (must be >= 1).
        do_sample: Enable stochastic sampling instead of deterministic greedy decoding.
        temperature: Sampling temperature (requires ``do_sample=True`` and > 0).
        model_id: Hugging Face model repository ID or local directory.
        device: Optional device selector (``"auto"``, ``"cuda"``, ``"mps"``, ``"cpu"``).
        token: Optional Hugging Face access token.

    Returns:
        A ``GenerationResult`` containing the decoded text and token counts.

    Raises:
        ValueError: If ``prompt`` is blank, ``max_new_tokens < 1``, or
            ``temperature`` is invalid.
    """
    if not prompt.strip():
        raise ValueError("prompt must be a non-empty string.")
    if max_new_tokens < 1:
        raise ValueError("max_new_tokens must be at least 1.")
    if temperature is not None:
        if temperature <= 0:
            raise ValueError("temperature must be positive.")
        if not do_sample:
            raise ValueError("temperature can only be set when do_sample=True.")

    tokenizer, model, resolved_device, dtype = load_model(
        model_id=model_id,
        device=device,
        token=token,
    )
    inputs = tokenizer(prompt, return_tensors="pt").to(resolved_device)
    input_token_count = int(inputs["input_ids"].shape[-1])
    pad_token_id = (
        tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    )

    generate_kwargs: dict[str, Any] = {
        "max_new_tokens": max_new_tokens,
        "do_sample": do_sample,
        "pad_token_id": pad_token_id,
    }
    if do_sample and temperature is not None:
        generate_kwargs["temperature"] = temperature

    with torch.inference_mode():
        outputs = model.generate(**inputs, **generate_kwargs)

    output_ids = outputs[0]
    generated_token_count = max(0, int(output_ids.shape[-1]) - input_token_count)
    generated_text = tokenizer.decode(output_ids, skip_special_tokens=True)
    return GenerationResult(
        model_id=model_id,
        device=str(resolved_device),
        dtype=str(dtype),
        prompt=prompt,
        generated_text=generated_text,
        input_token_count=input_token_count,
        generated_token_count=generated_token_count,
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the SmolLM2 CLI."""
    parser = argparse.ArgumentParser(
        description="Generate text with HuggingFaceTB/SmolLM2-360M.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Input prompt text to continue.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=DEFAULT_MAX_NEW_TOKENS,
        help="Maximum number of new tokens to generate (default: %(default)s).",
    )
    parser.add_argument(
        "--do-sample",
        action="store_true",
        help="Use stochastic sampling instead of deterministic greedy decoding.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Sampling temperature (requires --do-sample).",
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
    """Run the SmolLM2 text generation CLI.

    Args:
        argv: Optional command-line argument sequence. Defaults to ``sys.argv[1:]``.

    Returns:
        Process exit status code (``0`` on success).
    """
    args = build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose)
    result = generate_text(
        prompt=args.prompt,
        max_new_tokens=args.max_new_tokens,
        do_sample=args.do_sample,
        temperature=args.temperature,
        model_id=args.model_id,
        device=args.device,
    )
    print(result.generated_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
