"""Automatic speech recognition demo using openai/whisper-large-v3."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

import torch
from datasets import load_dataset
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, Pipeline, pipeline

from week_9.config import configure_logging, get_hf_token, resolve_device, resolve_dtype

LOGGER = logging.getLogger(__name__)

MODEL_ID: Final[str] = "openai/whisper-large-v3"
DEFAULT_DATASET_ID: Final[str] = "distil-whisper/librispeech_long"
DEFAULT_DATASET_CONFIG: Final[str] = "clean"
DEFAULT_DATASET_SPLIT: Final[str] = "validation"

WhisperTask = Literal["transcribe", "translate"]


@dataclass(frozen=True, slots=True)
class TranscriptChunk:
    """Single timestamped segment produced by Whisper long-form decoding.

    Attributes:
        start_s: Segment start offset in seconds, or ``None`` if unavailable.
        end_s: Segment end offset in seconds, or ``None`` if unavailable.
        text: Segment transcript text.
    """

    start_s: float | None
    end_s: float | None
    text: str


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """Structured output returned by Whisper speech recognition.

    Attributes:
        model_id: Hugging Face model checkpoint identifier.
        device: Execution device string (for example, ``"cuda"`` or ``"cpu"``).
        dtype: Floating-point precision used for model weights.
        source: Local audio file path or dataset sample identifier.
        text: Full transcribed or translated text.
        chunks: Timestamped transcript chunks when ``return_timestamps=True``.
    """

    model_id: str
    device: str
    dtype: str
    source: str
    text: str
    chunks: tuple[TranscriptChunk, ...]


def load_pipeline(
    *,
    model_id: str = MODEL_ID,
    device: str | None = None,
    token: str | None = None,
) -> tuple[Pipeline, torch.device, torch.dtype]:
    """Load the Whisper model, processor, and ASR pipeline onto the resolved device.

    Clears deprecated ``forced_decoder_ids`` from the model's generation config
    and disables WordPiece space cleanup on Whisper's BPE tokenizer to avoid
    deprecation warnings and punctuation corruption in Transformers 5.x.

    Args:
        model_id: Hugging Face model repository ID or local directory.
        device: Optional device selector (``"auto"``, ``"cuda"``, ``"mps"``, ``"cpu"``).
        token: Optional Hugging Face access token. Defaults to ``HF_TOKEN`` from
            the environment or ``Week_9/.env``.

    Returns:
        Tuple of ``(asr_pipeline, resolved_device, dtype)``.
    """
    resolved_token = token if token is not None else get_hf_token()
    resolved_device = resolve_device(device)
    dtype = resolve_dtype(resolved_device, prefer_bfloat16=False)

    LOGGER.info("Loading %s on %s (%s)", model_id, resolved_device, dtype)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id,
        dtype=dtype,
        low_cpu_mem_usage=True,
        use_safetensors=True,
        token=resolved_token,
    )
    model.to(resolved_device)
    model.eval()
    if getattr(model, "generation_config", None) is not None:
        model.generation_config.forced_decoder_ids = None

    processor = AutoProcessor.from_pretrained(
        model_id,
        token=resolved_token,
        clean_up_tokenization_spaces=False,
    )
    processor.tokenizer.clean_up_tokenization_spaces = False

    asr_pipeline = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        dtype=dtype,
        device=resolved_device,
    )
    return asr_pipeline, resolved_device, dtype


def load_sample_audio(
    *,
    dataset_id: str = DEFAULT_DATASET_ID,
    dataset_config: str = DEFAULT_DATASET_CONFIG,
    split: str = DEFAULT_DATASET_SPLIT,
    sample_index: int = 0,
    token: str | None = None,
) -> Any:
    """Load an audio sample from the default LibriSpeech Long validation dataset.

    Args:
        dataset_id: Hugging Face dataset repository ID.
        dataset_config: Dataset configuration / subset name.
        split: Dataset split name.
        sample_index: Zero-based row index to extract.
        token: Optional Hugging Face access token.

    Returns:
        The audio object at ``dataset[sample_index]["audio"]`` (for example, a
        ``torchcodec`` ``AudioDecoder`` or decoded audio dictionary).

    Raises:
        ValueError: If ``sample_index < 0``.
    """
    if sample_index < 0:
        raise ValueError("sample_index must be non-negative.")
    resolved_token = token if token is not None else get_hf_token()
    dataset = load_dataset(
        dataset_id,
        dataset_config,
        split=split,
        token=resolved_token,
    )
    return dataset[sample_index]["audio"]


def _parse_chunks(raw_chunks: object) -> tuple[TranscriptChunk, ...]:
    """Convert raw Transformers ASR chunk dictionaries into typed objects."""
    if not isinstance(raw_chunks, Sequence) or isinstance(raw_chunks, (str, bytes)):
        return ()

    parsed: list[TranscriptChunk] = []
    for item in raw_chunks:
        if not isinstance(item, dict):
            continue
        ts = item.get("timestamp")
        start_s: float | None = None
        end_s: float | None = None
        if isinstance(ts, Sequence) and len(ts) == 2:
            start_s = float(ts[0]) if ts[0] is not None else None
            end_s = float(ts[1]) if ts[1] is not None else None
        parsed.append(
            TranscriptChunk(
                start_s=start_s,
                end_s=end_s,
                text=str(item.get("text", "")).strip(),
            )
        )
    return tuple(parsed)


def transcribe_audio(
    audio_path: str | Path | None = None,
    *,
    return_timestamps: bool = True,
    task: WhisperTask = "transcribe",
    language: str | None = "en",
    sample_index: int = 0,
    model_id: str = MODEL_ID,
    device: str | None = None,
    token: str | None = None,
) -> TranscriptionResult:
    """Transcribe or translate speech audio using Whisper Large v3.

    When ``audio_path`` is ``None``, loads the sample recording from
    ``distil-whisper/librispeech_long`` (validation split).

    Args:
        audio_path: Optional path to a local audio file (WAV, FLAC, MP3, etc.).
        return_timestamps: Enable segment-level timestamps (required for
            long-form audio exceeding 30 seconds).
        task: Whisper task mode: ``"transcribe"`` or ``"translate"`` (to English).
        language: ISO language code (for example, ``"en"``) or ``None`` for
            automatic language detection.
        sample_index: Dataset row index used when ``audio_path`` is ``None``.
        model_id: Hugging Face model repository ID or local directory.
        device: Optional device selector (``"auto"``, ``"cuda"``, ``"mps"``, ``"cpu"``).
        token: Optional Hugging Face access token.

    Returns:
        A ``TranscriptionResult`` with the full transcript and optional chunks.

    Raises:
        ValueError: If ``task`` is invalid or ``sample_index < 0``.
        FileNotFoundError: If ``audio_path`` does not point to an existing file.
    """
    if task not in {"transcribe", "translate"}:
        raise ValueError("task must be either 'transcribe' or 'translate'.")

    resolved_token = token if token is not None else get_hf_token()
    if audio_path is not None:
        path = Path(audio_path)
        if not path.is_file():
            raise FileNotFoundError(f"Audio file not found: {path}")
        audio_input: Any = str(path)
        source_label = str(path)
    else:
        audio_input = load_sample_audio(sample_index=sample_index, token=resolved_token)
        source_label = (
            f"{DEFAULT_DATASET_ID}/{DEFAULT_DATASET_CONFIG}[{DEFAULT_DATASET_SPLIT}:{sample_index}]"
        )

    asr_pipeline, resolved_device, dtype = load_pipeline(
        model_id=model_id,
        device=device,
        token=resolved_token,
    )

    generate_kwargs: dict[str, Any] = {"task": task}
    if language:
        generate_kwargs["language"] = language

    with torch.inference_mode():
        raw_result = asr_pipeline(
            audio_input,
            return_timestamps=return_timestamps,
            generate_kwargs=generate_kwargs,
        )

    return TranscriptionResult(
        model_id=model_id,
        device=str(resolved_device),
        dtype=str(dtype),
        source=source_label,
        text=str(raw_result["text"]).strip(),
        chunks=_parse_chunks(raw_result.get("chunks")),
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the Whisper ASR CLI."""
    parser = argparse.ArgumentParser(
        description="Transcribe speech audio using openai/whisper-large-v3.",
    )
    parser.add_argument(
        "--audio",
        type=Path,
        default=None,
        help="Path to a local audio file. Defaults to the LibriSpeech Long validation sample.",
    )
    parser.add_argument(
        "--sample-index",
        type=int,
        default=0,
        help="Dataset sample index when --audio is not provided (default: %(default)s).",
    )
    parser.add_argument(
        "--task",
        choices=("transcribe", "translate"),
        default="transcribe",
        help="Whisper task mode (default: %(default)s).",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="ISO language code or 'auto' for automatic detection (default: %(default)s).",
    )
    parser.add_argument(
        "--no-timestamps",
        action="store_true",
        help="Disable timestamp prediction (only suitable for clips under 30 seconds).",
    )
    parser.add_argument(
        "--show-timestamps",
        action="store_true",
        help="Print timestamped chunks instead of a single paragraph.",
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
    """Run the Whisper speech recognition CLI.

    Args:
        argv: Optional command-line argument sequence. Defaults to ``sys.argv[1:]``.

    Returns:
        Process exit status code (``0`` on success).
    """
    args = build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose)
    language = None if args.language.strip().lower() == "auto" else args.language.strip()
    result = transcribe_audio(
        audio_path=args.audio,
        return_timestamps=not args.no_timestamps,
        task=args.task,
        language=language,
        sample_index=args.sample_index,
        model_id=args.model_id,
        device=args.device,
    )
    if args.show_timestamps and result.chunks:
        for chunk in result.chunks:
            start = f"{chunk.start_s:6.2f}s" if chunk.start_s is not None else "  ?.??s"
            end = f"{chunk.end_s:6.2f}s" if chunk.end_s is not None else "  ?.??s"
            print(f"[{start} -> {end}] {chunk.text}")
    else:
        print(result.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
