"""Chapter 2 tokenizer and model demonstrations for EE471 Week 9 Task 4.

Implements the five hands-on exercises from Chapter 2 of the Hugging Face LLM Course
using ``google-bert/bert-base-cased``:

1. Loading and saving a model and tokenizer locally (``save_pretrained`` / ``from_pretrained``).
2. WordPiece text encoding and decoding (``tokenize``, ``encode``, ``decode``).
3. Batch input padding and ``attention_mask`` alignment.
4. Overlength sequence truncation with ``max_length``.
5. Adding special tokens — both BERT's automatic ``[CLS]`` / ``[SEP]`` boundary tokens
   and registering a custom special token (``<EE471>``) with embedding-matrix resizing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

import torch
from transformers import (
    AutoModelForMaskedLM,
    AutoTokenizer,
    PreTrainedModel,
    PreTrainedTokenizerBase,
)

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
    """Before-and-after evidence for ``save_pretrained`` and local reload.

    Attributes:
        model_id: Source Hugging Face checkpoint identifier.
        save_dir: Local filesystem directory where artifacts were written.
        saved_files: Sorted filenames created by ``save_pretrained``.
        prompt: Masked input sentence used to verify numerical equivalence.
        before_token: Top predicted masked token before saving.
        before_score: Softmax probability of ``before_token`` before saving.
        after_token: Top predicted masked token after ``local_files_only=True`` reload.
        after_score: Softmax probability of ``after_token`` after reload.
        predictions_match: ``True`` when the reloaded model reproduces the prediction.
    """

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
    """Observable tokenization, integer IDs, and decoded text.

    Attributes:
        model_id: Hugging Face tokenizer checkpoint identifier.
        original_text: Raw input string before tokenization.
        tokens: WordPiece subword tokens produced by ``tokenizer.tokenize``.
        input_ids: Encoded integer token IDs including ``[CLS]`` and ``[SEP]``.
        decoded_with_special: Output of ``decode(..., skip_special_tokens=False)``.
        decoded_without_special: Output of ``decode(..., skip_special_tokens=True)``.
        explanation: Concise summary of boundary tokens and ``##`` subword merging.
    """

    model_id: str
    original_text: str
    tokens: tuple[str, ...]
    input_ids: tuple[int, ...]
    decoded_with_special: str
    decoded_without_special: str
    explanation: str


@dataclass(frozen=True, slots=True)
class PaddingResult:
    """Batch padding alignment evidence across multiple sentences.

    Attributes:
        model_id: Hugging Face tokenizer checkpoint identifier.
        sentences: Cleaned input sentences batched together.
        pad_token: Tokenizer padding symbol (``"[PAD]"`` for BERT).
        pad_token_id: Integer vocabulary ID corresponding to ``pad_token`` (``0`` for BERT).
        input_ids: Rectangular 2D tuple of padded token IDs.
        attention_masks: Rectangular 2D tuple of attention mask values (``1`` vs ``0``).
        shorter_row_index: Batch row index of the shortest input sequence.
        pad_positions: Column indices in ``shorter_row_index`` padded with ``pad_token_id``.
    """

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
    """Full vs truncated token length and retained token slice.

    Attributes:
        model_id: Hugging Face tokenizer checkpoint identifier.
        max_length: Maximum token budget passed to ``tokenizer.encode``
            (includes ``[CLS]`` and ``[SEP]``).
        full_length: Unconstrained token count of the full passage.
        truncated_length: Token count after applying ``truncation=True, max_length=max_length``.
        dropped_tokens: Number of tokens removed by truncation.
        retained_tokens: WordPiece tokens kept in the truncated sequence.
        truncated_text: Clean string decoded from the truncated token IDs.
    """

    model_id: str
    max_length: int
    full_length: int
    truncated_length: int
    dropped_tokens: int
    retained_tokens: tuple[str, ...]
    truncated_text: str


@dataclass(frozen=True, slots=True)
class SpecialTokensResult:
    """Evidence of automatic ``[CLS]``/``[SEP]`` addition and custom special-token resizing.

    Attributes:
        model_id: Hugging Face checkpoint identifier.
        special_token: Custom special token registered via ``add_special_tokens``.
        sample_text: Input sentence containing ``special_token``.
        tokens_before: Encoded tokens (with ``[CLS]``/``[SEP]``) before
            registering ``special_token``.
        tokens_after: Encoded tokens after registering ``special_token`` as an atomic symbol.
        special_token_id: New integer ID assigned to ``special_token``.
        vocab_size_before: Tokenizer length prior to adding ``special_token``.
        vocab_size_after: Tokenizer length after adding ``special_token``.
        embedding_rows_before: Model input embedding row count before ``resize_token_embeddings``.
        embedding_rows_after: Model input embedding row count after ``resize_token_embeddings``.
        ids_without_boundary: Raw token IDs from ``convert_tokens_to_ids(tokenize(sample_text))``
            without automatic ``[CLS]`` and ``[SEP]`` boundary tokens.
        ids_with_boundary: Full ``encode(sample_text)`` IDs showing ``[CLS]`` (101) and
            ``[SEP]`` (102) added automatically at the sequence boundaries.
        decoded_with_boundary: Decoded string retaining ``[CLS]`` and ``[SEP]``.
    """

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
    ids_without_boundary: tuple[int, ...] = ()
    ids_with_boundary: tuple[int, ...] = ()
    decoded_with_boundary: str = ""


def _predict_top_mask(
    tokenizer: PreTrainedTokenizerBase,
    model: PreTrainedModel,
    prompt: str,
    device: torch.device,
) -> tuple[str, float]:
    """Return the highest-probability masked token and softmax score for ``prompt``.

    Args:
        tokenizer: Loaded masked-LM tokenizer defining ``mask_token_id``.
        model: Loaded masked-LM model placed on ``device`` in evaluation mode.
        prompt: Input string containing exactly one ``tokenizer.mask_token``.
        device: Execution device for tensor inputs.

    Returns:
        Tuple ``(best_token_str, best_probability)``.

    Raises:
        ValueError: If ``prompt`` does not tokenize to exactly one mask position.
    """
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    mask_positions = (inputs["input_ids"][0] == tokenizer.mask_token_id).nonzero(as_tuple=False)
    if mask_positions.numel() != 1:
        raise ValueError(
            f"Expected exactly one mask token in prompt {prompt!r}; found {mask_positions.numel()}."
        )
    mask_idx = int(mask_positions[0].item())
    with torch.inference_mode():
        logits = model(**inputs).logits[0, mask_idx]
    probs = torch.softmax(logits.float(), dim=-1)
    best_id = int(torch.argmax(probs).item())
    token_str = str(tokenizer.decode([best_id], skip_special_tokens=True)).strip()
    return token_str, float(probs[best_id].item())


def demonstrate_load_and_save(
    save_dir: Path | None = None,
    *,
    prompt: str = DEFAULT_LOAD_SAVE_PROMPT,
    model_id: str = FILL_MASK_MODEL_ID,
    device: str | None = None,
) -> LoadSaveResult:
    """Load BERT, run inference, save via ``save_pretrained``, and reload offline.

    Args:
        save_dir: Optional directory where ``config.json``, ``model.safetensors``, and
            tokenizer files are written. When ``None``, uses an ephemeral temporary
            directory so no weights pollute the repository or Hub cache.
        prompt: Masked sentence used to verify identical predictions before and after reload.
        model_id: Masked LM checkpoint ID (defaults to ``google-bert/bert-base-cased``).
        device: Optional PyTorch device selector.

    Returns:
        A :class:`LoadSaveResult` listing saved files and confirming prediction parity.

    Raises:
        ValueError: If ``prompt`` does not contain exactly one ``[MASK]`` token.
        RuntimeError: If ``model_id`` cannot be loaded.
    """
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
    """Encode ``text`` into WordPiece tokens and integer IDs, then decode back.

    Args:
        text: Non-empty input string to tokenize, encode, and decode.
        model_id: Tokenizer checkpoint ID (defaults to ``google-bert/bert-base-cased``).

    Returns:
        An :class:`EncodeDecodeResult` showing subword pieces, IDs, and decoded text.

    Raises:
        ValueError: If ``text`` is empty or whitespace-only.
        RuntimeError: If the tokenizer cannot be loaded.
    """
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
    """Batch uneven-length sentences with ``padding=True`` and inspect ``attention_mask``.

    Args:
        sentences: At least two non-empty sentences of differing token lengths.
        model_id: Tokenizer checkpoint ID (defaults to ``google-bert/bert-base-cased``).

    Returns:
        A :class:`PaddingResult` highlighting ``[PAD]`` IDs and ``0`` mask entries.

    Raises:
        ValueError: If fewer than two non-empty sentences are supplied.
        RuntimeError: If the tokenizer cannot be loaded.
    """
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
    """Compare unconstrained tokenization against ``truncation=True`` with ``max_length``.

    Args:
        text: Long input text to encode before and after truncation.
        max_length: Maximum token count including ``[CLS]`` and ``[SEP]`` (must be ``>= 3``).
        model_id: Tokenizer checkpoint ID (defaults to ``google-bert/bert-base-cased``).

    Returns:
        A :class:`TruncationResult` reporting full vs truncated lengths and kept tokens.

    Raises:
        ValueError: If ``text`` is blank or ``max_length < 3``.
        RuntimeError: If the tokenizer cannot be loaded.
    """
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
    """Demonstrate BERT's automatic ``[CLS]``/``[SEP]`` boundary tokens and custom special tokens.

    Covers both Chapter 2 special-token mechanisms on isolated model/tokenizer copies:
    1. Contrasting manual ``convert_tokens_to_ids(tokenize(sample_text))`` (no boundary
       tokens) with ``encode(sample_text)`` (which automatically prepends ``[CLS]`` and
       appends ``[SEP]``).
    2. Registering ``special_token`` via ``add_special_tokens`` and calling
       ``model.resize_token_embeddings(len(tokenizer))`` so the embedding matrix matches
       the expanded vocabulary.

    Args:
        special_token: Custom atomic token string to register (for example, ``"<EE471>"``).
        sample_text: Example sentence containing ``special_token``.
        model_id: Masked LM checkpoint ID (defaults to ``google-bert/bert-base-cased``).

    Returns:
        A :class:`SpecialTokensResult` capturing boundary IDs, subword collapse, and
        vocabulary/embedding dimensions before and after registration.

    Raises:
        ValueError: If ``special_token`` is empty or whitespace-only.
        RuntimeError: If the checkpoint cannot be loaded.
    """
    cleaned_tok = special_token.strip()
    if not cleaned_tok:
        raise ValueError("special_token must be non-empty.")
    token = get_hf_token()
    tokenizer = load_pretrained_with_context(AutoTokenizer.from_pretrained, model_id, token=token)
    model = load_pretrained_with_context(
        AutoModelForMaskedLM.from_pretrained, model_id, token=token
    )
    model.eval()

    # Part 1 (Chapter 2.3 / 2.6): Compare raw token IDs without boundary tokens against
    # full encoding where BERT automatically adds [CLS] (101) and [SEP] (102).
    raw_pieces = tokenizer.tokenize(sample_text)
    raw_ids_any = tokenizer.convert_tokens_to_ids(raw_pieces)
    ids_without_boundary = (
        (int(raw_ids_any),) if isinstance(raw_ids_any, int) else tuple(int(x) for x in raw_ids_any)
    )
    ids_before = [int(x) for x in tokenizer.encode(sample_text)]
    ids_with_boundary = tuple(ids_before)
    decoded_with_boundary = str(tokenizer.decode(ids_before, skip_special_tokens=False))

    # Part 2: Register a custom special token and resize the model's input embeddings.
    vocab_before = len(tokenizer)
    embed_before = int(model.get_input_embeddings().weight.shape[0])
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
        ids_without_boundary=ids_without_boundary,
        ids_with_boundary=ids_with_boundary,
        decoded_with_boundary=decoded_with_boundary,
    )
