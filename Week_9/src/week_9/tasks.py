"""Shared object-oriented inference engine for all EE471 Week 9 tasks."""

from __future__ import annotations

import contextlib
import gc
import logging
import re
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import torch
from PIL import Image
from transformers import (
    AutoModelForCausalLM,
    AutoModelForMaskedLM,
    AutoModelForQuestionAnswering,
    AutoModelForSeq2SeqLM,
    AutoModelForSequenceClassification,
    AutoModelForSpeechSeq2Seq,
    AutoModelForTokenClassification,
    AutoProcessor,
    AutoTokenizer,
    ViTForImageClassification,
    ViTImageProcessor,
    pipeline,
)

from week_9.config import get_hf_token, resolve_device, resolve_dtype
from week_9.opus_mt_fr_en import TranslationResult
from week_9.vit import ClassificationResult, Prediction, load_image
from week_9.whisper import TranscriptChunk, TranscriptionResult, _parse_chunks

LOGGER = logging.getLogger(__name__)

SENTIMENT_MODEL_ID: Final[str] = "distilbert/distilbert-base-uncased-finetuned-sst-2-english"
ZERO_SHOT_MODEL_ID: Final[str] = "typeform/distilbert-base-uncased-mnli"
GENERATION_MODEL_ID: Final[str] = "HuggingFaceTB/SmolLM2-360M"
FILL_MASK_MODEL_ID: Final[str] = "google-bert/bert-base-cased"
NER_MODEL_ID: Final[str] = "dslim/bert-base-NER"
QA_MODEL_ID: Final[str] = "deepset/roberta-base-squad2"
T5_MODEL_ID: Final[str] = "google-t5/t5-small"
TRANSLATION_MODEL_ID: Final[str] = "Helsinki-NLP/opus-mt-fr-en"
VIT_MODEL_ID: Final[str] = "google/vit-base-patch16-224"
WHISPER_MODEL_ID: Final[str] = "openai/whisper-large-v3"

DEFAULT_SENTIMENT_TEXTS: Final[tuple[str, str]] = (
    "I've been waiting for a modern software practices course my whole life.",
    "I hate software courses",
)
DEFAULT_ZERO_SHOT_TEXT: Final[str] = (
    "Berkshire keeps their cash reserves at an extremely high level."
)
DEFAULT_ZERO_SHOT_LABELS: Final[tuple[str, ...]] = (
    "finance",
    "technology",
    "sports",
    "politics",
)
DEFAULT_GENERATION_PROMPT: Final[str] = (
    "If I continue to complete all in-class exercises in this modern software practices course,"
)
DEFAULT_GENERATION_MAX_WORDS: Final[int] = 35
DEFAULT_GENERATION_NUM_SENTENCES: Final[int] = 2
DEFAULT_FILL_MASK_TEXT: Final[str] = "To understand generative AI, one must study […] well."
DEFAULT_NER_QA_CONTEXT: Final[str] = (
    "I am Nate, a research assistant at Izmir Institute of Technology, "
    "and currently living and working in the beautiful city İzmir in Türkiye."
)
DEFAULT_QA_QUESTIONS: Final[tuple[str, str, str]] = (
    "What is the research assistant's name?",
    "At which institution does the research assistant work?",
    "In which city does the research assistant live?",
)
DEFAULT_SUMMARIZATION_TEXT: Final[str] = (
    "The 2008 Global Financial Crisis stands as the most severe economic collapse of the "
    "21st century, often compared to the Great Depression of the 1930s. Triggered by the "
    "bursting of the United States housing bubble, its effects rippled across the globe, "
    "leading to the collapse of major financial institutions and a deep international "
    "recession. The crisis began with the subprime mortgage market. In the early 2000s, "
    "low interest rates and a push for homeownership led banks to issue high-risk loans "
    "to borrowers with poor credit."
)
DEFAULT_TRANSLATION_TEXT: Final[str] = "Ce cours est produit par Hugging Face."

ASSETS_DIR: Final[Path] = Path(__file__).resolve().parent / "assets"
DEFAULT_IMAGE_PATH: Final[Path] = ASSETS_DIR / "dog.jpg"
DEFAULT_AUDIO_PATH: Final[Path] = ASSETS_DIR / "librispeech_sample.wav"

_GAP_PATTERN: Final[re.Pattern[str]] = re.compile(r"\[(?:…|\.{3}|MASK)\]")
_SENTENCE_END_PATTERN: Final[re.Pattern[str]] = re.compile(r"[.!?](?=\s|$)")


@dataclass(frozen=True, slots=True)
class SentimentItem:
    """Single sentence sentiment prediction."""

    text: str
    label: str
    score: float


@dataclass(frozen=True, slots=True)
class SentimentAnalysisResult:
    """Structured output returned by sentiment analysis."""

    model_id: str
    device: str
    items: tuple[SentimentItem, ...]


@dataclass(frozen=True, slots=True)
class ZeroShotScore:
    """Single candidate label score from zero-shot NLI classification."""

    label: str
    score: float


@dataclass(frozen=True, slots=True)
class ZeroShotResult:
    """Structured output returned by zero-shot classification."""

    model_id: str
    device: str
    text: str
    labels: tuple[ZeroShotScore, ...]


@dataclass(frozen=True, slots=True)
class GeneratedCompletion:
    """Single complete generated sentence within the word budget."""

    text: str
    word_count: int


@dataclass(frozen=True, slots=True)
class TextGenerationTaskResult:
    """Structured output returned by constrained text generation."""

    model_id: str
    device: str
    prompt: str
    max_words: int
    completions: tuple[GeneratedCompletion, ...]


@dataclass(frozen=True, slots=True)
class MaskCandidate:
    """Single ranked candidate token for mask filling."""

    token_str: str
    token_id: int
    score: float
    sequence: str


@dataclass(frozen=True, slots=True)
class FillMaskResult:
    """Structured output returned by mask filling."""

    model_id: str
    device: str
    text: str
    masked_text: str
    candidates: tuple[MaskCandidate, ...]


@dataclass(frozen=True, slots=True)
class NamedEntity:
    """Grouped named entity span sliced from the original source string."""

    text: str
    entity_group: str
    score: float
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class NerResult:
    """Structured output returned by named entity recognition."""

    model_id: str
    device: str
    text: str
    entities: tuple[NamedEntity, ...]


@dataclass(frozen=True, slots=True)
class QaValidationItem:
    """Question answering prediction paired with its corresponding NER span."""

    question: str
    answer: str
    score: float
    start: int
    end: int
    ner_entity: str | None
    ner_group: str | None
    agreed: bool


@dataclass(frozen=True, slots=True)
class QaValidationResult:
    """Structured output returned by extractive QA validation against NER."""

    model_id: str
    ner_model_id: str
    device: str
    context: str
    entities: tuple[NamedEntity, ...]
    items: tuple[QaValidationItem, ...]


@dataclass(frozen=True, slots=True)
class SummarizationResult:
    """Structured output returned by T5 summarization."""

    model_id: str
    device: str
    source_text: str
    summary_text: str


@dataclass(frozen=True, slots=True)
class EnFrTranslationResult:
    """Structured output returned by T5 English-to-French translation."""

    model_id: str
    device: str
    source_text: str
    translated_text: str


def load_pretrained_with_context[T](
    loader_fn: Callable[..., T],
    model_id: str,
    /,
    *args: Any,
    **kwargs: Any,
) -> T:
    """Call a Hugging Face ``from_pretrained`` loader with clear offline errors."""
    try:
        return loader_fn(model_id, *args, **kwargs)
    except OSError as exc:
        raise RuntimeError(
            f"Unable to load checkpoint '{model_id}'. If running offline "
            f"(HF_HUB_OFFLINE=1), populate the local cache by running once with "
            f"network access enabled. Original error: {exc}"
        ) from exc


def _parse_text_list(texts: Sequence[str] | str, *, field_name: str = "texts") -> tuple[str, ...]:
    if isinstance(texts, str):
        items = [line.strip() for line in texts.splitlines() if line.strip()]
    else:
        items = [str(item).strip() for item in texts if str(item).strip()]
    if not items:
        raise ValueError(f"{field_name} must contain at least one non-empty string.")
    return tuple(items)


def _parse_candidate_labels(labels: Sequence[str] | str) -> tuple[str, ...]:
    raw_items = labels.split(",") if isinstance(labels, str) else list(labels)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        cleaned = str(item).strip()
        if cleaned and cleaned.casefold() not in seen:
            seen.add(cleaned.casefold())
            deduped.append(cleaned)
    if not deduped:
        raise ValueError("candidate_labels must contain at least one non-empty label.")
    return tuple(deduped)


def _resolve_entailment_index(config: Any) -> int:
    label2id = getattr(config, "label2id", None) or {}
    for label, idx in label2id.items():
        if str(label).strip().lower() == "entailment":
            return int(idx)
    id2label = getattr(config, "id2label", None) or {}
    for idx, label in id2label.items():
        if str(label).strip().lower() == "entailment":
            return int(idx)
    raise RuntimeError(f"Could not find an 'entailment' label in model config: {label2id}")


def _extract_bounded_sentence(prompt: str, continuation: str, *, max_words: int) -> str | None:
    """Combine ``prompt`` and ``continuation`` and trim to a complete sentence <= ``max_words``."""
    suffix = " ".join(continuation.split())
    if not suffix:
        return None
    spacer = "" if prompt.endswith((" ", "\t", "\n")) else " "
    combined = f"{prompt}{spacer}{suffix}"
    prompt_word_count = len(prompt.split())

    for match in _SENTENCE_END_PATTERN.finditer(combined):
        end_pos = match.end()
        if end_pos <= len(prompt):
            continue
        # Skip numbered list markers like "1." or "2." or list-intro colons
        if match.group(0) == "." and end_pos >= 2 and combined[end_pos - 2].isdigit():
            continue
        candidate = combined[:end_pos].strip()
        if ":" in candidate[len(prompt) :]:
            continue
        words = candidate.split()
        if prompt_word_count < len(words) <= max_words:
            return candidate
    return None


def _expected_ner_group(question: str) -> str | None:
    lowered = question.lower()
    if any(kw in lowered for kw in ("name", "who", "person", "assistant's name")):
        return "PER"
    if any(kw in lowered for kw in ("institution", "company", "organization", "work")):
        return "ORG"
    if any(kw in lowered for kw in ("city", "where", "live", "country", "location")):
        return "LOC"
    return None


def _match_ner_for_qa(
    question: str,
    qa_start: int,
    qa_end: int,
    entities: Sequence[NamedEntity],
) -> NamedEntity | None:
    expected_group = _expected_ner_group(question)
    overlapping = [
        entity for entity in entities if max(qa_start, entity.start) < min(qa_end, entity.end)
    ]
    if expected_group is not None:
        for entity in overlapping:
            if entity.entity_group == expected_group:
                return entity
        for entity in entities:
            if entity.entity_group == expected_group:
                return entity
    if overlapping:
        return overlapping[0]
    return None


class Week9Tasks:
    """Object-oriented inference runner for all ten Week 9 Hugging Face tasks.

    Maintains at most one active model bundle in memory at a time so sequential
    CLI runs and concurrent Gradio requests fit comfortably within a 6 GB GPU.
    """

    def __init__(self, *, device: str | None = None, token: str | None = None) -> None:
        """Initialize the shared Week 9 task runner without loading any models.

        Args:
            device: Optional PyTorch device override (``"auto"``, ``"cuda"``,
                ``"mps"``, or ``"cpu"``).
            token: Optional Hugging Face Hub access token. Defaults to
                ``HF_TOKEN`` from the environment or ``Week_9/.env``.
        """
        self._device_pref = device
        self._token = token
        self._lock = threading.RLock()
        self._active_key: tuple[str, str, str] | None = None
        self._active_bundle: Any = None

    @property
    def active_model_key(self) -> tuple[str, str, str] | None:
        """Return the currently loaded ``(kind, model_id, device)`` key, if any."""
        return self._active_key

    def _resolved_token(self) -> str | None:
        return self._token if self._token is not None else get_hf_token()

    def unload_active_model(self) -> None:
        """Release the currently cached model bundle and reclaim GPU memory."""
        with self._lock:
            bundle = self._active_bundle
            self._active_bundle = None
            self._active_key = None
            if bundle is None:
                return
            if isinstance(bundle, dict):
                for value in bundle.values():
                    model_obj = getattr(value, "model", value)
                    if hasattr(model_obj, "to") and callable(model_obj.to):
                        with contextlib.suppress(Exception):
                            model_obj.to("cpu")
            del bundle
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def _get_bundle(
        self,
        kind: str,
        model_id: str,
        loader: Callable[[torch.device, str | None], dict[str, Any]],
    ) -> tuple[dict[str, Any], torch.device]:
        device = resolve_device(self._device_pref)
        key = (kind, model_id, str(device))
        if self._active_key == key and isinstance(self._active_bundle, dict):
            return self._active_bundle, device

        self.unload_active_model()
        LOGGER.info("Loading %s (%s) on %s", model_id, kind, device)
        bundle = loader(device, self._resolved_token())
        self._active_key = key
        self._active_bundle = bundle
        return bundle, device

    def _load_seq2seq_bundle(
        self,
        model_id: str,
        device: torch.device,
        token: str | None,
    ) -> dict[str, Any]:
        tokenizer = load_pretrained_with_context(
            AutoTokenizer.from_pretrained, model_id, token=token
        )
        model = load_pretrained_with_context(
            AutoModelForSeq2SeqLM.from_pretrained, model_id, token=token
        )
        model.to(device)
        model.eval()
        return {"tokenizer": tokenizer, "model": model}

    def analyze_sentiment(
        self,
        texts: Sequence[str] | str = DEFAULT_SENTIMENT_TEXTS,
        *,
        model_id: str = SENTIMENT_MODEL_ID,
    ) -> SentimentAnalysisResult:
        """Classify sentiment for one or more sentences in order."""
        parsed_texts = _parse_text_list(texts, field_name="texts")

        def _load(device: torch.device, token: str | None) -> dict[str, Any]:
            tokenizer = load_pretrained_with_context(
                AutoTokenizer.from_pretrained, model_id, token=token
            )
            model = load_pretrained_with_context(
                AutoModelForSequenceClassification.from_pretrained, model_id, token=token
            )
            model.to(device)
            model.eval()
            return {"tokenizer": tokenizer, "model": model}

        with self._lock:
            bundle, device = self._get_bundle("sentiment", model_id, _load)
            tokenizer = bundle["tokenizer"]
            model = bundle["model"]
            inputs = tokenizer(
                list(parsed_texts),
                padding=True,
                truncation=True,
                return_tensors="pt",
            ).to(device)
            with torch.inference_mode():
                logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1).cpu()
            id2label = getattr(model.config, "id2label", {})
            items: list[SentimentItem] = []
            for text, row in zip(parsed_texts, probs, strict=True):
                best_idx = int(torch.argmax(row).item())
                label = str(id2label.get(best_idx, best_idx))
                items.append(
                    SentimentItem(text=text, label=label, score=float(row[best_idx].item()))
                )
            return SentimentAnalysisResult(
                model_id=model_id,
                device=str(device),
                items=tuple(items),
            )

    def classify_zero_shot(
        self,
        text: str = DEFAULT_ZERO_SHOT_TEXT,
        candidate_labels: Sequence[str] | str = DEFAULT_ZERO_SHOT_LABELS,
        *,
        hypothesis_template: str = "This example is {}.",
        model_id: str = ZERO_SHOT_MODEL_ID,
    ) -> ZeroShotResult:
        """Rank ``candidate_labels`` for ``text`` using NLI entailment scores."""
        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("text must be a non-empty string.")
        parsed_labels = _parse_candidate_labels(candidate_labels)

        def _load(device: torch.device, token: str | None) -> dict[str, Any]:
            tokenizer = load_pretrained_with_context(
                AutoTokenizer.from_pretrained, model_id, token=token
            )
            model = load_pretrained_with_context(
                AutoModelForSequenceClassification.from_pretrained, model_id, token=token
            )
            model.to(device)
            model.eval()
            return {"tokenizer": tokenizer, "model": model}

        with self._lock:
            bundle, device = self._get_bundle("zero-shot", model_id, _load)
            tokenizer = bundle["tokenizer"]
            model = bundle["model"]
            entailment_idx = _resolve_entailment_index(model.config)
            hypotheses = [hypothesis_template.format(label) for label in parsed_labels]
            inputs = tokenizer(
                [cleaned_text] * len(parsed_labels),
                hypotheses,
                padding=True,
                truncation=True,
                return_tensors="pt",
            ).to(device)
            with torch.inference_mode():
                logits = model(**inputs).logits
            entailment_logits = logits[:, entailment_idx].float().cpu()
            scores = torch.softmax(entailment_logits, dim=0)
            ranked = sorted(
                (
                    ZeroShotScore(label=label, score=float(score.item()))
                    for label, score in zip(parsed_labels, scores, strict=True)
                ),
                key=lambda item: item.score,
                reverse=True,
            )
            return ZeroShotResult(
                model_id=model_id,
                device=str(device),
                text=cleaned_text,
                labels=tuple(ranked),
            )

    def complete_text(
        self,
        prompt: str = DEFAULT_GENERATION_PROMPT,
        *,
        max_words: int = DEFAULT_GENERATION_MAX_WORDS,
        num_sentences: int = DEFAULT_GENERATION_NUM_SENTENCES,
        model_id: str = GENERATION_MODEL_ID,
    ) -> TextGenerationTaskResult:
        """Generate ``num_sentences`` distinct complete sentences within ``max_words``."""
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            raise ValueError("prompt must be a non-empty string.")
        if max_words < 1:
            raise ValueError("max_words must be at least 1.")
        if num_sentences < 1:
            raise ValueError("num_sentences must be at least 1.")

        prompt_words = cleaned_prompt.split()
        if len(prompt_words) >= max_words:
            raise ValueError(
                f"Prompt already has {len(prompt_words)} words, which consumes the entire "
                f"budget of {max_words} words. Shorten the prompt or increase max_words."
            )

        def _load(device: torch.device, token: str | None) -> dict[str, Any]:
            dtype = resolve_dtype(device, prefer_bfloat16=True)
            tokenizer = load_pretrained_with_context(
                AutoTokenizer.from_pretrained, model_id, token=token
            )
            model = load_pretrained_with_context(
                AutoModelForCausalLM.from_pretrained,
                model_id,
                dtype=dtype,
                token=token,
            )
            model.to(device)
            model.eval()
            return {"tokenizer": tokenizer, "model": model}

        with self._lock:
            bundle, device = self._get_bundle("generate", model_id, _load)
            tokenizer = bundle["tokenizer"]
            model = bundle["model"]
            inputs = tokenizer(cleaned_prompt, return_tensors="pt").to(device)
            input_len = int(inputs["input_ids"].shape[-1])
            pad_token_id = (
                tokenizer.pad_token_id
                if tokenizer.pad_token_id is not None
                else tokenizer.eos_token_id
            )
            num_beams = max(6, num_sentences * 3)
            max_new_tokens = max(24, (max_words - len(prompt_words)) * 3)

            with torch.inference_mode():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    num_beams=num_beams,
                    num_return_sequences=num_beams,
                    do_sample=False,
                    no_repeat_ngram_size=3,
                    pad_token_id=pad_token_id,
                )

            completions: list[GeneratedCompletion] = []
            seen: set[str] = set()
            for seq in outputs:
                cont_ids = seq[input_len:]
                continuation = tokenizer.decode(cont_ids, skip_special_tokens=True)
                sentence = _extract_bounded_sentence(
                    cleaned_prompt, continuation, max_words=max_words
                )
                if sentence and sentence.casefold() not in seen:
                    seen.add(sentence.casefold())
                    completions.append(
                        GeneratedCompletion(text=sentence, word_count=len(sentence.split()))
                    )
                    if len(completions) >= num_sentences:
                        break

            if len(completions) < num_sentences:
                with torch.inference_mode():
                    sampled = model.generate(
                        **inputs,
                        max_new_tokens=max_new_tokens,
                        do_sample=True,
                        temperature=0.8,
                        top_p=0.95,
                        num_return_sequences=max(6, num_sentences * 4),
                        no_repeat_ngram_size=3,
                        pad_token_id=pad_token_id,
                    )
                for seq in sampled:
                    cont_ids = seq[input_len:]
                    continuation = tokenizer.decode(cont_ids, skip_special_tokens=True)
                    sentence = _extract_bounded_sentence(
                        cleaned_prompt, continuation, max_words=max_words
                    )
                    if sentence and sentence.casefold() not in seen:
                        seen.add(sentence.casefold())
                        completions.append(
                            GeneratedCompletion(text=sentence, word_count=len(sentence.split()))
                        )
                        if len(completions) >= num_sentences:
                            break

            if len(completions) < num_sentences:
                raise RuntimeError(
                    f"Could not produce {num_sentences} distinct complete sentences within "
                    f"{max_words} words."
                )

            return TextGenerationTaskResult(
                model_id=model_id,
                device=str(device),
                prompt=cleaned_prompt,
                max_words=max_words,
                completions=tuple(completions[:num_sentences]),
            )

    def fill_mask(
        self,
        text: str = DEFAULT_FILL_MASK_TEXT,
        *,
        top_k: int = 5,
        model_id: str = FILL_MASK_MODEL_ID,
    ) -> FillMaskResult:
        """Predict top-``k`` replacements for a single ``[…]`` or ``[MASK]`` gap."""
        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("text must be a non-empty string.")
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        matches = _GAP_PATTERN.findall(cleaned_text)
        if len(matches) != 1:
            raise ValueError(
                f"Input must contain exactly one mask placeholder ('[…]', '[...]', or '[MASK]'); "
                f"found {len(matches)}."
            )

        def _load(device: torch.device, token: str | None) -> dict[str, Any]:
            tokenizer = load_pretrained_with_context(
                AutoTokenizer.from_pretrained, model_id, token=token
            )
            model = load_pretrained_with_context(
                AutoModelForMaskedLM.from_pretrained, model_id, token=token
            )
            model.to(device)
            model.eval()
            return {"tokenizer": tokenizer, "model": model}

        with self._lock:
            bundle, device = self._get_bundle("fill-mask", model_id, _load)
            tokenizer = bundle["tokenizer"]
            model = bundle["model"]
            mask_token = str(tokenizer.mask_token)
            masked_text = _GAP_PATTERN.sub(mask_token, cleaned_text, count=1)
            inputs = tokenizer(masked_text, return_tensors="pt").to(device)
            mask_positions = (inputs["input_ids"][0] == tokenizer.mask_token_id).nonzero(
                as_tuple=False
            )
            if mask_positions.numel() != 1:
                raise ValueError("Tokenized input must contain exactly one mask token.")
            mask_idx = int(mask_positions[0].item())

            with torch.inference_mode():
                logits = model(**inputs).logits[0, mask_idx]
            probs = torch.softmax(logits.float(), dim=-1).cpu()
            k = min(top_k, int(probs.shape[-1]))
            top_probs, top_ids = torch.topk(probs, k=k)

            candidates: list[MaskCandidate] = []
            for prob, tok_id in zip(top_probs.tolist(), top_ids.tolist(), strict=True):
                token_str = str(tokenizer.decode([int(tok_id)], skip_special_tokens=True)).strip()
                sequence = masked_text.replace(mask_token, token_str, 1)
                candidates.append(
                    MaskCandidate(
                        token_str=token_str,
                        token_id=int(tok_id),
                        score=float(prob),
                        sequence=sequence,
                    )
                )

            return FillMaskResult(
                model_id=model_id,
                device=str(device),
                text=cleaned_text,
                masked_text=masked_text,
                candidates=tuple(candidates),
            )

    def recognize_entities(
        self,
        text: str = DEFAULT_NER_QA_CONTEXT,
        *,
        model_id: str = NER_MODEL_ID,
    ) -> NerResult:
        """Extract grouped named entities preserving exact Unicode source spans."""
        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("text must be a non-empty string.")

        def _load(device: torch.device, token: str | None) -> dict[str, Any]:
            tokenizer = load_pretrained_with_context(
                AutoTokenizer.from_pretrained, model_id, use_fast=True, token=token
            )
            model = load_pretrained_with_context(
                AutoModelForTokenClassification.from_pretrained, model_id, token=token
            )
            model.to(device)
            model.eval()
            return {"tokenizer": tokenizer, "model": model}

        with self._lock:
            bundle, device = self._get_bundle("ner", model_id, _load)
            tokenizer = bundle["tokenizer"]
            model = bundle["model"]
            encoding = tokenizer(
                cleaned_text,
                return_offsets_mapping=True,
                return_tensors="pt",
                truncation=True,
            )
            offsets = encoding["offset_mapping"][0].tolist()
            word_ids = encoding.word_ids(0)
            model_inputs = {
                key: value.to(device) for key, value in encoding.items() if key != "offset_mapping"
            }

            with torch.inference_mode():
                logits = model(**model_inputs).logits[0]
            probs = torch.softmax(logits.float(), dim=-1).cpu()
            id2label = getattr(model.config, "id2label", {})

            entities: list[NamedEntity] = []
            current_group: str | None = None
            current_start = 0
            current_end = 0
            current_scores: list[float] = []
            current_word_id: int | None = None

            def _flush() -> None:
                nonlocal current_group, current_start, current_end, current_scores
                if current_group is not None and current_end > current_start:
                    avg_score = sum(current_scores) / len(current_scores)
                    entities.append(
                        NamedEntity(
                            text=cleaned_text[current_start:current_end],
                            entity_group=current_group,
                            score=float(avg_score),
                            start=current_start,
                            end=current_end,
                        )
                    )
                current_group = None
                current_start = 0
                current_end = 0
                current_scores = []

            for idx, (offset, word_id) in enumerate(zip(offsets, word_ids, strict=True)):
                start_char, end_char = int(offset[0]), int(offset[1])
                if word_id is None or start_char == end_char:
                    _flush()
                    current_word_id = None
                    continue

                best_idx = int(torch.argmax(probs[idx]).item())
                tag = str(id2label.get(best_idx, "O"))
                score = float(probs[idx, best_idx].item())

                if tag == "O":
                    # Keep subwords of an active multi-piece word together if they share word_id
                    if current_group is not None and word_id == current_word_id:
                        current_end = end_char
                        continue
                    _flush()
                    current_word_id = word_id
                    continue

                prefix, _, group = tag.partition("-")
                if not group:
                    group = prefix
                    prefix = "B"

                same_word = current_group is not None and word_id == current_word_id
                can_continue = current_group == group and (prefix == "I" or same_word)
                if can_continue:
                    current_end = end_char
                    current_scores.append(score)
                else:
                    _flush()
                    current_group = group
                    current_start = start_char
                    current_end = end_char
                    current_scores = [score]
                current_word_id = word_id

            _flush()
            return NerResult(
                model_id=model_id,
                device=str(device),
                text=cleaned_text,
                entities=tuple(entities),
            )

    def answer_question(
        self,
        questions: Sequence[str] | str = DEFAULT_QA_QUESTIONS,
        context: str = DEFAULT_NER_QA_CONTEXT,
        *,
        model_id: str = QA_MODEL_ID,
        ner_model_id: str = NER_MODEL_ID,
    ) -> QaValidationResult:
        """Answer extractive questions and compare answers against NER spans."""
        cleaned_context = context.strip()
        if not cleaned_context:
            raise ValueError("context must be a non-empty string.")
        parsed_questions = _parse_text_list(questions, field_name="questions")

        def _load(device: torch.device, token: str | None) -> dict[str, Any]:
            tokenizer = load_pretrained_with_context(
                AutoTokenizer.from_pretrained, model_id, use_fast=True, token=token
            )
            model = load_pretrained_with_context(
                AutoModelForQuestionAnswering.from_pretrained, model_id, token=token
            )
            model.to(device)
            model.eval()
            return {"tokenizer": tokenizer, "model": model}

        with self._lock:
            ner_result = self.recognize_entities(cleaned_context, model_id=ner_model_id)
            bundle, device = self._get_bundle("qa", model_id, _load)
            tokenizer = bundle["tokenizer"]
            model = bundle["model"]

            items: list[QaValidationItem] = []
            for question in parsed_questions:
                encoding = tokenizer(
                    question,
                    cleaned_context,
                    return_offsets_mapping=True,
                    return_tensors="pt",
                    truncation="only_second",
                )
                offsets = encoding["offset_mapping"][0].tolist()
                sequence_ids = encoding.sequence_ids(0)
                model_inputs = {
                    key: value.to(device)
                    for key, value in encoding.items()
                    if key != "offset_mapping"
                }

                with torch.inference_mode():
                    outputs = model(**model_inputs)
                start_logits = outputs.start_logits[0].float().cpu()
                end_logits = outputs.end_logits[0].float().cpu()

                context_mask = torch.tensor(
                    [seq_id == 1 for seq_id in sequence_ids], dtype=torch.bool
                )
                neg_inf = torch.tensor(-1e9)
                masked_start = torch.where(context_mask, start_logits, neg_inf)
                masked_end = torch.where(context_mask, end_logits, neg_inf)
                start_probs = torch.softmax(masked_start, dim=-1)
                end_probs = torch.softmax(masked_end, dim=-1)

                context_indices = [i for i, is_ctx in enumerate(context_mask.tolist()) if is_ctx]
                best_score = -1.0
                best_start = context_indices[0]
                best_end = context_indices[0]
                for s_idx in context_indices:
                    for e_idx in range(s_idx, min(s_idx + 30, context_indices[-1] + 1)):
                        if not context_mask[e_idx]:
                            continue
                        pair_score = float((start_probs[s_idx] * end_probs[e_idx]).item())
                        if pair_score > best_score:
                            best_score = pair_score
                            best_start = s_idx
                            best_end = e_idx

                char_start = int(offsets[best_start][0])
                char_end = int(offsets[best_end][1])
                answer = cleaned_context[char_start:char_end].strip()
                matched_ner = _match_ner_for_qa(question, char_start, char_end, ner_result.entities)
                ner_text = matched_ner.text if matched_ner is not None else None
                ner_group = matched_ner.entity_group if matched_ner is not None else None
                agreed = bool(
                    ner_text is not None
                    and answer.strip().casefold() == ner_text.strip().casefold()
                )
                items.append(
                    QaValidationItem(
                        question=question,
                        answer=answer,
                        score=float(best_score),
                        start=char_start,
                        end=char_end,
                        ner_entity=ner_text,
                        ner_group=ner_group,
                        agreed=agreed,
                    )
                )

            return QaValidationResult(
                model_id=model_id,
                ner_model_id=ner_model_id,
                device=str(device),
                context=cleaned_context,
                entities=ner_result.entities,
                items=tuple(items),
            )

    def summarize(
        self,
        text: str = DEFAULT_SUMMARIZATION_TEXT,
        *,
        max_new_tokens: int = 80,
        min_length: int = 20,
        model_id: str = T5_MODEL_ID,
    ) -> SummarizationResult:
        """Summarize ``text`` using ``google-t5/t5-small`` via ``AutoModelForSeq2SeqLM``."""
        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("text must be a non-empty string.")
        if max_new_tokens < 1:
            raise ValueError("max_new_tokens must be at least 1.")

        with self._lock:
            bundle, device = self._get_bundle(
                "seq2seq",
                model_id,
                lambda dev, tok: self._load_seq2seq_bundle(model_id, dev, tok),
            )
            tokenizer = bundle["tokenizer"]
            model = bundle["model"]
            inputs = tokenizer(
                f"summarize: {cleaned_text}",
                return_tensors="pt",
                truncation=True,
            ).to(device)
            with torch.inference_mode():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    min_length=min_length,
                    num_beams=4,
                    length_penalty=2.0,
                    early_stopping=True,
                    no_repeat_ngram_size=3,
                )
            summary = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
            return SummarizationResult(
                model_id=model_id,
                device=str(device),
                source_text=cleaned_text,
                summary_text=summary,
            )

    def translate_text(
        self,
        text: str = DEFAULT_TRANSLATION_TEXT,
        *,
        max_new_tokens: int = 128,
        model_id: str = TRANSLATION_MODEL_ID,
    ) -> TranslationResult:
        """Translate French ``text`` to English using ``Helsinki-NLP/opus-mt-fr-en``."""
        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("text must be a non-empty string.")
        if max_new_tokens < 1:
            raise ValueError("max_new_tokens must be at least 1.")

        def _load(dev: torch.device, tok: str | None) -> dict[str, Any]:
            bundle = self._load_seq2seq_bundle(model_id, dev, tok)
            model = bundle["model"]
            if getattr(model, "generation_config", None) is not None:
                model.generation_config.max_length = None
            return bundle

        with self._lock:
            bundle, device = self._get_bundle("seq2seq", model_id, _load)
            tokenizer = bundle["tokenizer"]
            model = bundle["model"]
            inputs = tokenizer(cleaned_text, return_tensors="pt", truncation=True).to(device)
            with torch.inference_mode():
                outputs = model.generate(**inputs, max_new_tokens=max_new_tokens)
            translated = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
            return TranslationResult(
                model_id=model_id,
                device=str(device),
                source_text=cleaned_text,
                translated_text=translated,
            )

    def translate_to_french(
        self,
        text: str = DEFAULT_SUMMARIZATION_TEXT,
        *,
        max_new_tokens: int = 128,
        model_id: str = T5_MODEL_ID,
    ) -> EnFrTranslationResult:
        """Translate English ``text`` to French using ``google-t5/t5-small``."""
        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("text must be a non-empty string.")
        if max_new_tokens < 1:
            raise ValueError("max_new_tokens must be at least 1.")

        with self._lock:
            bundle, device = self._get_bundle(
                "seq2seq",
                model_id,
                lambda dev, tok: self._load_seq2seq_bundle(model_id, dev, tok),
            )
            tokenizer = bundle["tokenizer"]
            model = bundle["model"]
            inputs = tokenizer(
                f"translate English to French: {cleaned_text}",
                return_tensors="pt",
                truncation=True,
            ).to(device)
            with torch.inference_mode():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    num_beams=4,
                    early_stopping=True,
                )
            translated = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
            return EnFrTranslationResult(
                model_id=model_id,
                device=str(device),
                source_text=cleaned_text,
                translated_text=translated,
            )

    def classify_image(
        self,
        image_source: str | Path | Image.Image = DEFAULT_IMAGE_PATH,
        *,
        top_k: int = 5,
        model_id: str = VIT_MODEL_ID,
    ) -> ClassificationResult:
        """Classify a local/URL/PIL image using ``google/vit-base-patch16-224``."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        if isinstance(image_source, Image.Image):
            image = image_source.convert("RGB")
            source_label = "<uploaded image>"
        else:
            if not str(image_source).strip():
                raise ValueError("image_source must not be empty.")
            image = load_image(image_source)
            source_label = str(image_source)

        def _load(device: torch.device, token: str | None) -> dict[str, Any]:
            processor = load_pretrained_with_context(
                ViTImageProcessor.from_pretrained, model_id, token=token
            )
            model = load_pretrained_with_context(
                ViTForImageClassification.from_pretrained, model_id, token=token
            )
            model.to(device)
            model.eval()
            return {"processor": processor, "model": model}

        with self._lock:
            bundle, device = self._get_bundle("vit", model_id, _load)
            processor = bundle["processor"]
            model = bundle["model"]
            inputs = processor(images=image, return_tensors="pt").to(device)
            with torch.inference_mode():
                logits = model(**inputs).logits
            probabilities = torch.softmax(logits, dim=-1)[0].cpu()
            k = min(top_k, int(probabilities.shape[-1]))
            top_probs, top_indices = torch.topk(probabilities, k=k)
            predictions = tuple(
                Prediction(
                    label=str(model.config.id2label[int(idx)]),
                    class_id=int(idx),
                    probability=float(prob),
                )
                for prob, idx in zip(top_probs.tolist(), top_indices.tolist(), strict=True)
            )
            return ClassificationResult(
                model_id=model_id,
                device=str(device),
                source=source_label,
                top_prediction=predictions[0],
                predictions=predictions,
            )

    def transcribe_audio(
        self,
        audio_source: str | Path | None = DEFAULT_AUDIO_PATH,
        *,
        return_timestamps: bool = True,
        language: str | None = "en",
        model_id: str = WHISPER_MODEL_ID,
    ) -> TranscriptionResult:
        """Transcribe an audio file using ``openai/whisper-large-v3``."""
        resolved_path = Path(audio_source) if audio_source is not None else DEFAULT_AUDIO_PATH
        if not resolved_path.is_file():
            raise FileNotFoundError(f"Audio file not found: {resolved_path}")

        def _load(device: torch.device, token: str | None) -> dict[str, Any]:
            dtype = resolve_dtype(device, prefer_bfloat16=False)
            model = load_pretrained_with_context(
                AutoModelForSpeechSeq2Seq.from_pretrained,
                model_id,
                dtype=dtype,
                low_cpu_mem_usage=True,
                use_safetensors=True,
                token=token,
            )
            model.to(device)
            model.eval()
            if getattr(model, "generation_config", None) is not None:
                model.generation_config.forced_decoder_ids = None
            processor = load_pretrained_with_context(
                AutoProcessor.from_pretrained,
                model_id,
                token=token,
                clean_up_tokenization_spaces=False,
            )
            processor.tokenizer.clean_up_tokenization_spaces = False
            asr_pipe = pipeline(
                "automatic-speech-recognition",
                model=model,
                tokenizer=processor.tokenizer,
                feature_extractor=processor.feature_extractor,
                dtype=dtype,
                device=device,
            )
            return {"pipeline": asr_pipe, "dtype": dtype}

        with self._lock:
            bundle, device = self._get_bundle("whisper", model_id, _load)
            asr_pipe = bundle["pipeline"]
            dtype = bundle["dtype"]
            generate_kwargs: dict[str, Any] = {"task": "transcribe"}
            if language:
                generate_kwargs["language"] = language

            with torch.inference_mode():
                raw_result = asr_pipe(
                    str(resolved_path),
                    return_timestamps=return_timestamps,
                    generate_kwargs=generate_kwargs,
                )

            chunks: tuple[TranscriptChunk, ...] = _parse_chunks(raw_result.get("chunks"))
            return TranscriptionResult(
                model_id=model_id,
                device=str(device),
                dtype=str(dtype),
                source=str(resolved_path),
                text=str(raw_result["text"]).strip(),
                chunks=chunks,
            )
