"""Shared environment, credential, logging, and PyTorch device helpers for Week 9."""

from __future__ import annotations

import logging
import os
import warnings
from pathlib import Path
from typing import Final

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from dotenv import load_dotenv
from transformers.utils import logging as hf_logging

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH: Final[Path] = PROJECT_ROOT / ".env"
HF_TOKEN_ENV_VAR: Final[str] = "HF_TOKEN"


def load_environment(env_path: Path | None = None, *, override: bool = False) -> Path | None:
    """Load environment variables from a local ``.env`` file.

    By default, variables already present in ``os.environ`` take precedence over
    values stored in ``.env`` (``override=False``).

    Args:
        env_path: Explicit path to a ``.env`` file. When ``None``, checks
            ``Week_9/.env`` first and then ``<cwd>/.env``.
        override: Whether values in the ``.env`` file should overwrite existing
            process environment variables.

    Returns:
        The resolved ``Path`` of the loaded ``.env`` file, or ``None`` if no
        ``.env`` file was found.
    """
    candidates = (env_path,) if env_path is not None else (DEFAULT_ENV_PATH, Path.cwd() / ".env")
    for candidate in candidates:
        if candidate.is_file():
            load_dotenv(dotenv_path=candidate, override=override)
            return candidate
    return None


def get_hf_token(*, env_path: Path | None = None, required: bool = False) -> str | None:
    """Retrieve the Hugging Face access token from ``HF_TOKEN`` or ``Week_9/.env``.

    Loading ``Week_9/.env`` also populates ``os.environ["HF_TOKEN"]``, which
    ``huggingface_hub``, ``transformers``, and ``datasets`` pick up automatically.

    Args:
        env_path: Optional explicit path to a ``.env`` file to load before
            reading ``HF_TOKEN``.
        required: If ``True``, raise ``RuntimeError`` when ``HF_TOKEN`` is unset
            or blank.

    Returns:
        The stripped token string, or ``None`` when not configured and
        ``required`` is ``False``.

    Raises:
        RuntimeError: If ``required`` is ``True`` and ``HF_TOKEN`` is missing.
    """
    load_environment(env_path=env_path)
    token = os.environ.get(HF_TOKEN_ENV_VAR, "").strip()
    if token:
        return token
    if required:
        raise RuntimeError(
            f"{HF_TOKEN_ENV_VAR} is not set. Create Week_9/.env and set "
            f"{HF_TOKEN_ENV_VAR} to your Hugging Face access token."
        )
    return None


def resolve_device(preferred: str | None = None) -> torch.device:
    """Select an available PyTorch execution device.

    Args:
        preferred: Optional device string such as ``"auto"``, ``"cuda"``,
            ``"cuda:0"``, ``"mps"``, or ``"cpu"``. When ``None`` or ``"auto"``,
            prefers CUDA, then Apple MPS, then CPU.

    Returns:
        A validated ``torch.device`` instance.

    Raises:
        RuntimeError: If ``cuda`` or ``mps`` was explicitly requested but is not
            available on the host machine.
    """
    normalized = preferred.strip().lower() if preferred else "auto"
    if normalized == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    device = torch.device(normalized)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(
            f"Requested device '{preferred}', but CUDA is not available on this machine."
        )
    if device.type == "mps" and not (
        hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    ):
        raise RuntimeError(
            f"Requested device '{preferred}', but MPS is not available on this machine."
        )
    return device


def resolve_dtype(device: torch.device, *, prefer_bfloat16: bool = False) -> torch.dtype:
    """Select an appropriate floating-point precision for inference on ``device``.

    Args:
        device: Target PyTorch execution device.
        prefer_bfloat16: Prefer ``torch.bfloat16`` over ``torch.float16`` on CUDA
            GPUs that support bfloat16 natively (for models trained in bfloat16).

    Returns:
        ``torch.bfloat16`` or ``torch.float16`` on CUDA, and ``torch.float32``
        on CPU/MPS.
    """
    if device.type == "cuda":
        if prefer_bfloat16 and torch.cuda.is_bf16_supported():
            return torch.bfloat16
        return torch.float16
    return torch.float32


def configure_logging(*, verbose: bool = False) -> None:
    """Configure concise CLI and library logging for the ``week_9`` package.

    When ``verbose`` is ``False``, silences Hugging Face ``transformers`` progress
    bars, checkpoint load-report tables, and benign Triton configuration warnings
    so CLI outputs remain clean and readable.

    Args:
        verbose: When ``True``, emit ``INFO`` logs for ``week_9`` and restore
            ``WARNING`` verbosity and progress bars for ``transformers``.
    """
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("week_9").setLevel(logging.INFO if verbose else logging.WARNING)
    if verbose:
        hf_logging.set_verbosity_warning()
        hf_logging.enable_progress_bar()
    else:
        hf_logging.set_verbosity_error()
        hf_logging.disable_progress_bar()
        warnings.filterwarnings("ignore", category=UserWarning, module=r"triton\..*")
