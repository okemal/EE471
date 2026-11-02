"""Download only the pinned safetensors weights for an offline demonstration."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.config import settings
from backend.app.model import download_models

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    download_models(settings)
    print("Both pinned checkpoints are cached. You can now use CAT_ID_OFFLINE=1.")
