"""Validated catalogue loader for the 10 FashionMNIST garment categories."""

import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "garments.json"


@lru_cache(maxsize=1)
def garment_catalogue() -> tuple[dict, ...]:
    """Load and validate the 10 FashionMNIST garment categories."""
    items = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if len(items) != 10:
        raise ValueError(f"Expected 10 FashionMNIST classes, found {len(items)}.")
    seen_ids: set[str] = set()
    seen_labels: set[str] = set()
    for expected_index, item in enumerate(items):
        if item["class_index"] != expected_index:
            raise ValueError(f"Class index mismatch at {expected_index}: {item['class_index']}")
        if item["id"] in seen_ids or item["label"] in seen_labels:
            raise ValueError(f"Duplicate garment entry: {item['id']}")
        seen_ids.add(item["id"])
        seen_labels.add(item["label"])
    return tuple(items)


def get_garment(garment_id: str) -> dict | None:
    """Look up a garment profile by slug ID."""
    return next((item for item in garment_catalogue() if item["id"] == garment_id), None)


def get_garment_by_index(class_index: int) -> dict | None:
    """Look up a garment profile by FashionMNIST integer index (0-9)."""
    return next((item for item in garment_catalogue() if item["class_index"] == class_index), None)


def get_garment_by_label(label: str) -> dict | None:
    """Look up a garment profile by exact FashionMNIST label."""
    return next((item for item in garment_catalogue() if item["label"] == label), None)
