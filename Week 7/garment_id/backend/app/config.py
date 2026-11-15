"""Explicit, environment-configurable settings for the garment classifier."""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Immutable application and inference configuration."""

    max_upload_bytes: int = 10 * 1024 * 1024
    max_pixels: int = 20_000_000
    max_dimension: int = 12_000
    min_dimension: int = 28
    device: str = os.getenv("GARMENT_ID_DEVICE", "auto")
    cache_dir: Path = Path(os.getenv("GARMENT_ID_MODEL_CACHE", str(ROOT / ".cache/models")))
    data_dir: Path = Path(os.getenv("GARMENT_ID_DATA_CACHE", str(ROOT / ".cache/data")))
    offline: bool = os.getenv("GARMENT_ID_OFFLINE", "0") == "1"
    load_model: bool = os.getenv("GARMENT_ID_LOAD_MODEL", "1") == "1"
    cog_url: str = os.getenv("GARMENT_ID_COG_URL", "")
    confident_min_probability: float = 0.55
    confident_min_margin: float = 0.12
    uncertain_min_probability: float = 0.30

    @classmethod
    def from_env(cls) -> "Settings":
        """Build a Settings instance from the current process environment."""
        return cls(
            device=os.getenv("GARMENT_ID_DEVICE", "auto"),
            cache_dir=Path(os.getenv("GARMENT_ID_MODEL_CACHE", str(ROOT / ".cache/models"))),
            data_dir=Path(os.getenv("GARMENT_ID_DATA_CACHE", str(ROOT / ".cache/data"))),
            offline=os.getenv("GARMENT_ID_OFFLINE", "0") == "1",
            load_model=os.getenv("GARMENT_ID_LOAD_MODEL", "1") == "1",
            cog_url=os.getenv("GARMENT_ID_COG_URL", ""),
        )


settings = Settings()
