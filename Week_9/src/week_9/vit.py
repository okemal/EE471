"""ImageNet-1K image classification demo using google/vit-base-patch16-224."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Final
from urllib.parse import urlparse

import requests
import torch
from PIL import Image
from transformers import ViTForImageClassification, ViTImageProcessor

from week_9.config import configure_logging, get_hf_token, resolve_device

LOGGER = logging.getLogger(__name__)

MODEL_ID: Final[str] = "google/vit-base-patch16-224"
# Note: images.cocodataset.org serves this official sample asset over HTTP only
# (HTTPS currently fails hostname certificate verification on that host).
DEFAULT_IMAGE_URL: Final[str] = "http://images.cocodataset.org/val2017/000000039769.jpg"
DEFAULT_TIMEOUT_SECONDS: Final[float] = 30.0
DEFAULT_TOP_K: Final[int] = 5


@dataclass(frozen=True, slots=True)
class Prediction:
    """Single ImageNet class prediction with calibrated softmax probability.

    Attributes:
        label: Human-readable ImageNet class label.
        class_id: Integer class index in ``model.config.id2label``.
        probability: Softmax probability in ``[0.0, 1.0]``.
    """

    label: str
    class_id: int
    probability: float


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Structured output returned by Vision Transformer image classification.

    Attributes:
        model_id: Hugging Face model checkpoint identifier.
        device: Execution device string (for example, ``"cuda"`` or ``"cpu"``).
        source: Image URL or local filesystem path that was classified.
        top_prediction: Highest-probability class prediction.
        predictions: Ranked tuple of top-k predictions.
    """

    model_id: str
    device: str
    source: str
    top_prediction: Prediction
    predictions: tuple[Prediction, ...]


def load_image(
    source: str | Path,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_SECONDS,
) -> Image.Image:
    """Load an RGB PIL image from an HTTP(S) URL or local file path.

    Args:
        source: HTTP(S) URL or local filesystem path to an image file.
        timeout_s: Network request timeout in seconds for URL downloads.

    Returns:
        A detached ``PIL.Image.Image`` converted to ``"RGB"`` mode.

    Raises:
        ValueError: If ``timeout_s <= 0``.
        FileNotFoundError: If ``source`` is a local path that does not exist.
        requests.HTTPError: If downloading a remote URL returns an error status.
    """
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive.")

    if isinstance(source, str) and urlparse(source).scheme in {"http", "https"}:
        LOGGER.info("Downloading image from %s", source)
        with requests.get(source, timeout=timeout_s) as response:
            response.raise_for_status()
            with Image.open(BytesIO(response.content)) as img:
                return img.convert("RGB")

    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"Image file not found: {path}")
    with Image.open(path) as img:
        return img.convert("RGB")


def load_model(
    *,
    model_id: str = MODEL_ID,
    device: str | None = None,
    token: str | None = None,
) -> tuple[ViTImageProcessor, ViTForImageClassification, torch.device]:
    """Load the ViT image processor and classifier onto the resolved device.

    Args:
        model_id: Hugging Face model repository ID or local directory.
        device: Optional device selector (``"auto"``, ``"cuda"``, ``"mps"``, ``"cpu"``).
        token: Optional Hugging Face access token. Defaults to ``HF_TOKEN`` from
            the environment or ``Week_9/.env``.

    Returns:
        Tuple of ``(processor, model, resolved_device)``.
    """
    resolved_token = token if token is not None else get_hf_token()
    resolved_device = resolve_device(device)

    LOGGER.info("Loading %s on %s", model_id, resolved_device)
    processor = ViTImageProcessor.from_pretrained(model_id, token=resolved_token)
    model = ViTForImageClassification.from_pretrained(model_id, token=resolved_token)
    model.to(resolved_device)
    model.eval()
    return processor, model, resolved_device


def classify_image(
    source: str | Path = DEFAULT_IMAGE_URL,
    *,
    top_k: int = DEFAULT_TOP_K,
    timeout_s: float = DEFAULT_TIMEOUT_SECONDS,
    model_id: str = MODEL_ID,
    device: str | None = None,
    token: str | None = None,
) -> ClassificationResult:
    """Classify an image into ImageNet-1K categories using ViT.

    Args:
        source: Image URL or local file path.
        top_k: Number of top-ranked predictions to return (must be >= 1).
        timeout_s: HTTP download timeout in seconds when ``source`` is a URL.
        model_id: Hugging Face model repository ID or local directory.
        device: Optional device selector (``"auto"``, ``"cuda"``, ``"mps"``, ``"cpu"``).
        token: Optional Hugging Face access token.

    Returns:
        A ``ClassificationResult`` with the top-1 and top-k predictions.

    Raises:
        ValueError: If ``top_k < 1`` or ``timeout_s <= 0``.
    """
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    image = load_image(source, timeout_s=timeout_s)
    processor, model, resolved_device = load_model(
        model_id=model_id,
        device=device,
        token=token,
    )

    inputs = processor(images=image, return_tensors="pt").to(resolved_device)
    with torch.inference_mode():
        logits = model(**inputs).logits

    probabilities = torch.softmax(logits, dim=-1)[0]
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
        device=str(resolved_device),
        source=str(source),
        top_prediction=predictions[0],
        predictions=predictions,
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the ViT image classification CLI."""
    parser = argparse.ArgumentParser(
        description="Classify an image using google/vit-base-patch16-224.",
    )
    parser.add_argument(
        "--image",
        default=DEFAULT_IMAGE_URL,
        help="Image URL or local file path (default: COCO sample cat photo).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="Number of top predictions to display (default: %(default)s).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP request timeout in seconds for URL inputs (default: %(default)s).",
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
    """Run the ViT image classification CLI.

    Args:
        argv: Optional command-line argument sequence. Defaults to ``sys.argv[1:]``.

    Returns:
        Process exit status code (``0`` on success).
    """
    args = build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose)
    result = classify_image(
        source=args.image,
        top_k=args.top_k,
        timeout_s=args.timeout,
        model_id=args.model_id,
        device=args.device,
    )
    top = result.top_prediction
    print(f"Predicted class: {top.label} ({top.probability:.2%})")
    if len(result.predictions) > 1:
        for rank, pred in enumerate(result.predictions, start=1):
            print(f"  {rank}. {pred.label}: {pred.probability:.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
