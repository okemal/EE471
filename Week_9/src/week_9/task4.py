"""Chapter 2 tokenizer and model demonstrations for EE471 Week 9 Task 4."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer

from week_9.config import get_hf_token, resolve_device
from week_9.tasks import (
    DEFAULT_SENTIMENT_TEXTS,
    DEFAULT_SUMMARIZATION_TEXT,
    FILL_MASK_MODEL_ID,
    load_pretrained_with_context,
)

DEFAULT_LOAD_SAVE_PROMPT: Final[str] = "To understand generative AI, one must study [MASK] well."
DEFAULT_ENCODE_DECODE_TEXT: Final[str] = (
    "To understand generative AI, one must study transformers well in İzmir."
)
DEFAULT_TRUNCATE_MAX_LENGTH: Final[int] = 16
DEFAULT_SPECIAL_TOKEN: Final[str] = "<EE471>"
DEFAULT_SPECIAL_TOKEN_TEXT: Final[str] = "Welcome to <EE471> at Izmir Institute of Technology!"


@dataclass(frozen=True, slots=True)
class LoadSaveResult:
    """Before-and-after evidence for ``save_pretrained`` and local reload."""

    model_id: str
    save_dir: str
    saved_files: tuple[str, ...]
    prompt: str
    before_token: str
    before_score: float
    after_token: str
    after_score: float
    predictions_match: bool


@dataclass(frozen=True, slots=True)
class EncodeDecodeResult:
    """Observable tokenization, integer IDs, and decoded text."""

    model_id: str
    original_text: str
    tokens: tuple[str, ...]
    input_ids: tuple[int, ...]
    decoded_with_special: str
    decoded_without_special: str
    explanation: str


@dataclass(frozen=True, slots=True)
class PaddingResult:
    """Batch padding alignment evidence across two sentences."""

    model_id: str
    sentences: tuple[str, ...]
    pad_token: str
    pad_token_id: int
    input_ids: tuple[tuple[int, ...], ...]
    attention_masks: tuple[tuple[int, ...], ...]
    shorter_row_index: int
    pad_positions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class TruncationResult:
    """Full vs truncated token length and retained token slice."""

    model_id: str
    max_length: int
    full_length: int
    truncated_length: int
    dropped_tokens: int
    retained_tokens: tuple[str, ...]
    truncated_text: str


@dataclass(frozen=True, slots=True)
class SpecialTokensResult:
    """Evidence of registering a custom special token and resizing embeddings."""

    model_id: str
    special_token: str
    sample_text: str
    tokens_before: tuple[str, ...]
    tokens_after: tuple[str, ...]
    special_token_id: int
    vocab_size_before: int
    vocab_size_after: int
    embedding_rows_before: int
    embedding_rows_after: int


def _predict_top_mask(
    tokenizer: object, model: object, prompt: str, device: torch.device
) -> tuple[str, float]:
    inputs = tokenizer(prompt, return_tensors="pt").to(device)  # type: ignore[operator]
    mask_positions = (inputs["input_ids"][0] == tokenizer.mask_token_id).nonzero(  # type: ignore[attr-defined]
        as_tuple=False
    )
    mask_idx = int(mask_positions[0].item())
    with torch.inference_mode():
        logits = model(**inputs).logits[0, mask_idx]  # type: ignore[operator]
    probs = torch.softmax(logits.float(), dim=-1)
    best_id = int(torch.argmax(probs).item())
    token_str = str(tokenizer.decode([best_id], skip_special_tokens=True)).strip()  # type: ignore[attr-defined]
    return token_str, float(probs[best_id].item())


def demonstrate_load_and_save(
    save_dir: Path | None = None,
    *,
    prompt: str = DEFAULT_LOAD_SAVE_PROMPT,
    model_id: str = FILL_MASK_MODEL_ID,
    device: str | None = None,
) -> LoadSaveResult:
    """Load BERT, predict, save via ``save_pretrained``, and reload offline."""
    token = get_hf_token()
    resolved_device = resolve_device(device)
    tokenizer = load_pretrained_with_context(AutoTokenizer.from_pretrained, model_id, token=token)
    model = load_pretrained_with_context(
        AutoModelForMaskedLM.from_pretrained, model_id, token=token
    )
    model.to(resolved_device)
    model.eval()

    before_token, before_score = _predict_top_mask(tokenizer, model, prompt, resolved_device)

    def _save_and_reload(target_dir: Path) -> LoadSaveResult:
        tokenizer.save_pretrained(target_dir)
        model.save_pretrained(target_dir)
        saved_files = tuple(sorted(p.name for p in target_dir.iterdir() if p.is_file()))

        reloaded_tok = AutoTokenizer.from_pretrained(target_dir, local_files_only=True)
        reloaded_model = AutoModelForMaskedLM.from_pretrained(target_dir, local_files_only=True)
        reloaded_model.to(resolved_device)
        reloaded_model.eval()
        after_token, after_score = _predict_top_mask(
            reloaded_tok, reloaded_model, prompt, resolved_device
        )
        return LoadSaveResult(
            model_id=model_id,
            save_dir=str(target_dir),
            saved_files=saved_files,
            prompt=prompt,
            before_token=before_token,
            before_score=before_score,
            after_token=after_token,
            after_score=after_score,
            predictions_match=(
                before_token == after_token and abs(before_score - after_score) < 1e-5
            ),
        )

    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)
        return _save_and_reload(save_dir)

    with TemporaryDirectory(prefix="week9_bert_") as tmp_dir:
        return _save_and_reload(Path(tmp_dir))


def demonstrate_encode_and_decode(
    text: str = DEFAULT_ENCODE_DECODE_TEXT,
    *,
    model_id: str = FILL_MASK_MODEL_ID,
) -> EncodeDecodeResult:
    """Encode ``text`` into WordPiece tokens and IDs, then decode back."""
    if not text.strip():
        raise ValueError("text must be a non-empty string.")
    token = get_hf_token()
    tokenizer = load_pretrained_with_context(AutoTokenizer.from_pretrained, model_id, token=token)
    pieces = tuple(tokenizer.tokenize(text))
    ids = tuple(int(x) for x in tokenizer.encode(text))
    decoded_with_special = str(tokenizer.decode(list(ids), skip_special_tokens=False))
    decoded_without_special = str(tokenizer.decode(list(ids), skip_special_tokens=True))
    explanation = (
        "encode() prepends [CLS] (101) and appends [SEP] (102); WordPiece splits rare or "
        "subword parts with '##' prefixes (for example, 'transform' + '##ers' or "
        "'İ' + '##z' + '##mir') and decode() merges them back into readable text."
    )
    return EncodeDecodeResult(
        model_id=model_id,
        original_text=text,
        tokens=pieces,
        input_ids=ids,
        decoded_with_special=decoded_with_special,
        decoded_without_special=decoded_without_special,
        explanation=explanation,
    )


def demonstrate_padding(
    sentences: Sequence[str] = DEFAULT_SENTIMENT_TEXTS,
    *,
    model_id: str = FILL_MASK_MODEL_ID,
) -> PaddingResult:
    """Batch two different-length sentences with padding and aligned attention masks."""
    cleaned = tuple(s.strip() for s in sentences if s.strip())
    if len(cleaned) < 2:
        raise ValueError("At least two non-empty sentences are required for padding.")
    token = get_hf_token()
    tokenizer = load_pretrained_with_context(AutoTokenizer.from_pretrained, model_id, token=token)
    batch = tokenizer(list(cleaned), padding=True, return_tensors="pt")
    input_ids = tuple(tuple(int(v) for v in row) for row in batch["input_ids"].tolist())
    masks = tuple(tuple(int(v) for v in row) for row in batch["attention_mask"].tolist())
    pad_id = int(tokenizer.pad_token_id)

    shorter_idx = min(range(len(masks)), key=lambda idx: sum(masks[idx]))
    pad_positions = tuple(
        pos
        for pos, (tok_id, mask_val) in enumerate(
            zip(input_ids[shorter_idx], masks[shorter_idx], strict=True)
        )
        if tok_id == pad_id and mask_val == 0
    )
    return PaddingResult(
        model_id=model_id,
        sentences=cleaned,
        pad_token=str(tokenizer.pad_token),
        pad_token_id=pad_id,
        input_ids=input_ids,
        attention_masks=masks,
        shorter_row_index=shorter_idx,
        pad_positions=pad_positions,
    )


def demonstrate_truncation(
    text: str = DEFAULT_SUMMARIZATION_TEXT,
    *,
    max_length: int = DEFAULT_TRUNCATE_MAX_LENGTH,
    model_id: str = FILL_MASK_MODEL_ID,
) -> TruncationResult:
    """Compare full-length encoding against truncated encoding with ``max_length``."""
    if not text.strip():
        raise ValueError("text must be a non-empty string.")
    if max_length < 3:
        raise ValueError("max_length must be at least 3 to retain [CLS] and [SEP].")
    token = get_hf_token()
    tokenizer = load_pretrained_with_context(AutoTokenizer.from_pretrained, model_id, token=token)
    full_ids = tokenizer.encode(text, truncation=False)
    trunc_ids = tokenizer.encode(text, truncation=True, max_length=max_length)
    retained_tokens = tuple(tokenizer.convert_ids_to_tokens(trunc_ids))
    truncated_text = str(tokenizer.decode(trunc_ids, skip_special_tokens=True))
    return TruncationResult(
        model_id=model_id,
        max_length=max_length,
        full_length=len(full_ids),
        truncated_length=len(trunc_ids),
        dropped_tokens=max(0, len(full_ids) - len(trunc_ids)),
        retained_tokens=retained_tokens,
        truncated_text=truncated_text,
    )


def demonstrate_special_tokens(
    special_token: str = DEFAULT_SPECIAL_TOKEN,
    sample_text: str = DEFAULT_SPECIAL_TOKEN_TEXT,
    *,
    model_id: str = FILL_MASK_MODEL_ID,
) -> SpecialTokensResult:
    """Register a custom special token and resize an exercise-local model's embeddings."""
    cleaned_tok = special_token.strip()
    if not cleaned_tok:
        raise ValueError("special_token must be non-empty.")
    token = get_hf_token()
    tokenizer = load_pretrained_with_context(AutoTokenizer.from_pretrained, model_id, token=token)
    model = load_pretrained_with_context(
        AutoModelForMaskedLM.from_pretrained, model_id, token=token
    )
    model.eval()

    vocab_before = len(tokenizer)
    embed_before = int(model.get_input_embeddings().weight.shape[0])
    ids_before = tokenizer.encode(sample_text)
    tokens_before = tuple(tokenizer.convert_ids_to_tokens(ids_before))

    tokenizer.add_special_tokens({"additional_special_tokens": [cleaned_tok]})
    model.resize_token_embeddings(len(tokenizer))

    vocab_after = len(tokenizer)
    embed_after = int(model.get_input_embeddings().weight.shape[0])
    ids_after = tokenizer.encode(sample_text)
    tokens_after = tuple(tokenizer.convert_ids_to_tokens(ids_after))
    special_token_id = int(tokenizer.convert_tokens_to_ids(cleaned_tok))

    return SpecialTokensResult(
        model_id=model_id,
        special_token=cleaned_tok,
        sample_text=sample_text,
        tokens_before=tokens_before,
        tokens_after=tokens_after,
        special_token_id=special_token_id,
        vocab_size_before=vocab_before,
        vocab_size_after=vocab_after,
        embedding_rows_before=embed_before,
        embedding_rows_after=embed_after,
    )
