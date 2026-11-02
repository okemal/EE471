"""Explicit, environment-configurable limits for the local application."""

from dataclasses import dataclass
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    max_upload_bytes: int = 10 * 1024 * 1024
    max_pixels: int = 20_000_000
    max_dimension: int = 12_000
    device: str = os.getenv("CAT_ID_DEVICE", "auto")
    cache_dir: Path = Path(os.getenv("CAT_ID_MODEL_CACHE", str(ROOT / ".cache/models")))
    offline: bool = os.getenv("CAT_ID_OFFLINE", "0") == "1"
    wikipedia_enabled: bool = os.getenv("CAT_ID_WIKIPEDIA", "1") == "1"
    load_model: bool = os.getenv("CAT_ID_LOAD_MODEL", "1") == "1"
    # Deliberately fixed, documented heuristics. They are not calibrated probabilities.
    gate_min_similarity: float = 0.23
    gate_min_margin: float = 0.015
    species_min_similarity: float = 0.20
    species_min_margin: float = 0.015


settings = Settings()
