"""Validated catalogue loader for the 10 CIFAR-10 image categories."""

import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "classes.json"


@lru_cache(maxsize=1)
def cifar_catalogue() -> tuple[dict, ...]:
    """Load and validate the 10 CIFAR-10 categories."""
    items = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if len(items) != 10:
        raise ValueError(f"Expected 10 CIFAR-10 classes, found {len(items)}.")
    seen_ids: set[str] = set()
    seen_labels: set[str] = set()
    for expected_index, item in enumerate(items):
        if item["class_index"] != expected_index:
            raise ValueError(f"Class index mismatch at {expected_index}: {item['class_index']}")
        if item["id"] in seen_ids or item["label"] in seen_labels:
            raise ValueError(f"Duplicate CIFAR-10 entry: {item['id']}")
        seen_ids.add(item["id"])
        seen_labels.add(item["label"])
    return tuple(items)


def get_cifar_class(class_id: str) -> dict | None:
    """Look up a CIFAR-10 class profile by slug ID."""
    return next((item for item in cifar_catalogue() if item["id"] == class_id), None)


def get_cifar_class_by_index(class_index: int) -> dict | None:
    """Look up a CIFAR-10 class profile by integer index (0-9)."""
    return next((item for item in cifar_catalogue() if item["class_index"] == class_index), None)


def get_cifar_class_by_label(label: str) -> dict | None:
    """Look up a CIFAR-10 class profile by canonical short label."""
    return next((item for item in cifar_catalogue() if item["label"] == label), None)
