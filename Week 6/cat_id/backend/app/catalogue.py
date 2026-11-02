"""Load the versioned, curated catalogue; never accept arbitrary upstream page names."""

import json
from functools import lru_cache
from pathlib import Path

from .schemas import Species


@lru_cache(maxsize=1)
def species_catalogue() -> list[dict]:
    records = json.loads((Path(__file__).parent / "data/species.json").read_text())
    records = [Species.model_validate(record).model_dump() for record in records]
    ids = [record["id"] for record in records]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate species identifiers in the catalogue")
    return records


def get_species(species_id: str) -> dict | None:
    return next((item for item in species_catalogue() if item["id"] == species_id), None)
