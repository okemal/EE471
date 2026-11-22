"""Official MediaPipe 1.2.3 model catalog and cached atomic downloader."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODELS_DIR = PROJECT_ROOT / ".cache" / "models"


@dataclass(frozen=True)
class ModelSpec:
    """Metadata for an official Hugging Face litert-community MediaPipe model bundle."""

    task: str
    domain: str
    filename: str
    url: str
    approx_mb: float
    description: str


MODEL_SPECS: dict[str, ModelSpec] = {
    # Audio (3)
    "audio_classifier": ModelSpec(
        task="audio_classifier",
        domain="audio",
        filename="yamnet.tflite",
        url=(
            "https://huggingface.co/litert-community/MediaPipe-AudioClassifier-YAMNet/"
            "resolve/main/yamnet.tflite"
        ),
        approx_mb=3.9,
        description="YAMNet 521-class AudioSet environmental sound classifier",
    ),
    "audio_transcriber": ModelSpec(
        task="audio_transcriber",
        domain="audio",
        filename="parakeet_tdt_0.6b_v3_5s_i8_stateful.litertlm",
        url=(
            "https://huggingface.co/litert-community/parakeet-tdt-0.6b-v3/"
            "resolve/main/parakeet_tdt_0.6b_v3_5s_i8_stateful.litertlm"
        ),
        approx_mb=586.1,
        description="Parakeet-TDT 0.6B v3 stateful int8 on-device speech transcriber",
    ),
    "text_to_speech": ModelSpec(
        task="text_to_speech",
        domain="audio",
        filename="phonon_int8.litertlm",
        url=(
            "https://huggingface.co/litert-community/phonon-31m-en/"
            "resolve/main/phonon_int8.litertlm"
        ),
        approx_mb=83.2,
        description="Phonon 31M English CPU-friendly neural text-to-speech model",
    ),
    # Decision (1)
    "decision_maker": ModelSpec(
        task="decision_maker",
        domain="decision",
        filename="embeddinggemma-2-text-270m.litertlm",
        url=(
            "https://huggingface.co/litert-community/embeddinggemma-2-text-270m-litert-lm/"
            "resolve/main/embeddinggemma-2-text-270m.litertlm"
        ),
        approx_mb=157.0,
        description="EmbeddingGemma-2 Text 270M zero-decoding decision engine",
    ),
    # Retrieval (2 — shared multimodal EmbeddingGemma-2 440M bundle)
    "semantic_retriever": ModelSpec(
        task="semantic_retriever",
        domain="retrieval",
        filename="embeddinggemma-2-text-vision-440m.litertlm",
        url=(
            "https://huggingface.co/litert-community/embeddinggemma-2-text-vision-440m-litert-lm/"
            "resolve/main/embeddinggemma-2-text-vision-440m.litertlm"
        ),
        approx_mb=369.8,
        description="EmbeddingGemma-2 Text+Vision 440M for on-device semantic retrieval",
    ),
    "universal_embedder": ModelSpec(
        task="universal_embedder",
        domain="retrieval",
        filename="embeddinggemma-2-text-vision-440m.litertlm",
        url=(
            "https://huggingface.co/litert-community/embeddinggemma-2-text-vision-440m-litert-lm/"
            "resolve/main/embeddinggemma-2-text-vision-440m.litertlm"
        ),
        approx_mb=369.8,
        description="EmbeddingGemma-2 Text+Vision 440M multimodal embedder",
    ),
    # Text (5)
    "language_detector": ModelSpec(
        task="language_detector",
        domain="text",
        filename="language_detector.tflite",
        url=(
            "https://huggingface.co/litert-community/MediaPipe-LanguageDetector/"
            "resolve/main/language_detector.tflite"
        ),
        approx_mb=0.3,
        description="MediaPipe 110-language text detector",
    ),
    "text_classifier": ModelSpec(
        task="text_classifier",
        domain="text",
        filename="bert_classifier.tflite",
        url=(
            "https://huggingface.co/litert-community/MediaPipe-TextClassifier-MobileBERT/"
            "resolve/main/bert_classifier.tflite"
        ),
        approx_mb=24.5,
        description="MobileBERT sentiment text classifier",
    ),
    "text_embedder": ModelSpec(
        task="text_embedder",
        domain="text",
        filename="universal_sentence_encoder.tflite",
        url=(
            "https://huggingface.co/litert-community/"
            "MediaPipe-TextEmbedder-Universal-Sentence-Encoder/"
            "resolve/main/universal_sentence_encoder.tflite"
        ),
        approx_mb=5.8,
        description="Universal Sentence Encoder text embedder",
    ),
    "text_proofreader": ModelSpec(
        task="text_proofreader",
        domain="text",
        filename="proofread_quant_200m.litertlm",
        url=(
            "https://huggingface.co/litert-community/MediaPipe-TextProofreader-200M/"
            "resolve/main/proofread_quant_200m.litertlm"
        ),
        approx_mb=112.1,
        description="MediaPipe 200M quantized on-device text proofreader",
    ),
    "text_summarizer": ModelSpec(
        task="text_summarizer",
        domain="text",
        filename="summarization_quant_200m_2modes.litertlm",
        url=(
            "https://huggingface.co/litert-community/MediaPipe-TextSummarizer-200M/"
            "resolve/main/summarization_quant_200m_2modes.litertlm"
        ),
        approx_mb=112.1,
        description="MediaPipe 200M quantized 2-mode text summarizer",
    ),
    # Vision (11)
    "face_detector": ModelSpec(
        task="face_detector",
        domain="vision",
        filename="blaze_face_short_range.tflite",
        url=(
            "https://huggingface.co/litert-community/"
            "MediaPipe-FaceDetector-BlazeFace-Short-Range/"
            "resolve/main/blaze_face_short_range.tflite"
        ),
        approx_mb=0.2,
        description="BlazeFace short-range 6-keypoint face detector",
    ),
    "face_landmarker": ModelSpec(
        task="face_landmarker",
        domain="vision",
        filename="face_landmarker.task",
        url=(
            "https://huggingface.co/litert-community/MediaPipe-FaceLandmarker/"
            "resolve/main/face_landmarker.task"
        ),
        approx_mb=3.6,
        description="MediaPipe 478-point FaceLandmarker with blendshapes and 4x4 pose matrix",
    ),
    "gesture_recognizer": ModelSpec(
        task="gesture_recognizer",
        domain="vision",
        filename="gesture_recognizer.task",
        url=(
            "https://huggingface.co/litert-community/MediaPipe-GestureRecognizer/"
            "resolve/main/gesture_recognizer.task"
        ),
        approx_mb=8.0,
        description="MediaPipe canned hand gesture recognizer",
    ),
    "hand_landmarker": ModelSpec(
        task="hand_landmarker",
        domain="vision",
        filename="hand_landmarker.task",
        url=(
            "https://huggingface.co/litert-community/MediaPipe-HandLandmarker-Full/"
            "resolve/main/hand_landmarker.task"
        ),
        approx_mb=7.5,
        description="MediaPipe 21-point 3D hand landmarker",
    ),
    "holistic_landmarker": ModelSpec(
        task="holistic_landmarker",
        domain="vision",
        filename="holistic_landmarker.task",
        url=(
            "https://huggingface.co/litert-community/MediaPipe-HolisticLandmarker/"
            "resolve/main/holistic_landmarker.task"
        ),
        approx_mb=13.0,
        description="MediaPipe unified pose + face + hands holistic landmarker",
    ),
    "image_classifier": ModelSpec(
        task="image_classifier",
        domain="vision",
        filename="efficientnet_lite0_int8.tflite",
        url=(
            "https://huggingface.co/litert-community/"
            "MediaPipe-ImageClassifier-EfficientNet-Lite0/"
            "resolve/main/efficientnet_lite0_int8.tflite"
        ),
        approx_mb=5.2,
        description="EfficientNet-Lite0 int8 ImageNet-1K image classifier",
    ),
    "image_embedder": ModelSpec(
        task="image_embedder",
        domain="vision",
        filename="mobilenet_v3_small.tflite",
        url=(
            "https://huggingface.co/litert-community/"
            "MediaPipe-ImageEmbedder-MobileNet-V3-Small/"
            "resolve/main/mobilenet_v3_small.tflite"
        ),
        approx_mb=3.9,
        description="MobileNet-V3 Small image embedding extractor",
    ),
    "image_segmenter": ModelSpec(
        task="image_segmenter",
        domain="vision",
        filename="deeplab_v3.tflite",
        url=(
            "https://huggingface.co/litert-community/MediaPipe-ImageSegmenter-DeepLab-V3/"
            "resolve/main/deeplab_v3.tflite"
        ),
        approx_mb=2.7,
        description="DeepLab-v3 PASCAL VOC 21-class semantic image segmenter",
    ),
    "interactive_segmenter": ModelSpec(
        task="interactive_segmenter",
        domain="vision",
        filename="interactive_segmentation.task",
        url=(
            "https://huggingface.co/litert-community/MediaPipe-InteractiveSegmenter-MagicTouch/"
            "resolve/main/interactive_segmentation.task"
        ),
        approx_mb=29.1,
        description="MagicTouch point/stroke interactive foreground segmenter",
    ),
    "object_detector": ModelSpec(
        task="object_detector",
        domain="vision",
        filename="efficientdet_lite0_float16.tflite",
        url=(
            "https://huggingface.co/litert-community/"
            "MediaPipe-ObjectDetector-EfficientDet-Lite0/"
            "resolve/main/efficientdet_lite0_float16.tflite"
        ),
        approx_mb=6.9,
        description="EfficientDet-Lite0 float16 COCO object detector",
    ),
    "pose_landmarker": ModelSpec(
        task="pose_landmarker",
        domain="vision",
        filename="pose_landmarker_full.task",
        url=(
            "https://huggingface.co/litert-community/MediaPipe-PoseLandmarker-Full/"
            "resolve/main/pose_landmarker_full.task"
        ),
        approx_mb=9.0,
        description="MediaPipe 33-point full pose landmarker",
    ),
}


def models_dir() -> Path:
    """Return the configured local model cache directory."""
    override = os.environ.get("MEDIAPIPE_DEMOS_MODEL_DIR")
    return Path(override) if override else DEFAULT_MODELS_DIR


def sha256_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file using 1 MiB chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_model(
    task: str, *, model_path: Path | None = None, cache_dir: Path | None = None
) -> Path:
    """Return a local path to the model for `task`, downloading atomically if absent."""
    if model_path is not None:
        resolved = Path(model_path)
        if not resolved.is_file():
            raise FileNotFoundError(f"Custom model path does not exist: {resolved}")
        return resolved

    if task not in MODEL_SPECS:
        raise KeyError(f"Unknown MediaPipe task {task!r}. Valid keys: {sorted(MODEL_SPECS)}")

    spec = MODEL_SPECS[task]
    target_dir = cache_dir or models_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / spec.filename
    if destination.is_file() and destination.stat().st_size > 0:
        return destination

    if os.environ.get("MEDIAPIPE_DEMOS_OFFLINE") == "1":
        raise FileNotFoundError(
            f"Offline mode enabled and cached model missing for {task}: {destination}"
        )

    part_path = destination.with_suffix(destination.suffix + ".part")
    print(f"[download] {task}: {spec.filename} (~{spec.approx_mb:.1f} MB) -> {destination}")
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(30.0, read=300.0)) as client:
        with client.stream("GET", spec.url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length") or 0)
            written = 0
            with part_path.open("wb") as handle:
                for chunk in response.iter_bytes(chunk_size=1024 * 256):
                    handle.write(chunk)
                    written += len(chunk)
    if total and written != total:
        part_path.unlink(missing_ok=True)
        raise RuntimeError(f"Incomplete download for {spec.filename}: got {written}/{total} bytes")
    part_path.replace(destination)
    print(f"[cached]   {spec.filename} ({written / (1024 * 1024):.1f} MB)")
    return destination


def download_all_models(cache_dir: Path | None = None) -> dict[str, Path]:
    """Ensure every unique model bundle required by the 22 tasks is cached locally."""
    resolved: dict[str, Path] = {}
    for task in MODEL_SPECS:
        resolved[task] = ensure_model(task, cache_dir=cache_dir)
    return resolved
