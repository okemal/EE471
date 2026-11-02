"""Small, deterministic open-set decision layer, independently testable without weights."""

from dataclasses import dataclass
from math import isfinite

from .config import Settings


@dataclass(frozen=True)
class Decision:
    status: str
    message: str


def decide(
    cat_similarity: float, other_similarity: float, species_scores: list[float], settings: Settings
) -> Decision:
    if not all(isfinite(value) for value in [cat_similarity, other_similarity, *species_scores]):
        raise ValueError("The model returned non-finite similarities")
    if (
        cat_similarity < settings.gate_min_similarity
        or cat_similarity - other_similarity < settings.gate_min_margin
    ):
        return Decision("no_match", "No reliable Felidae match was found in this photograph.")
    if (
        len(species_scores) < 2
        or species_scores[0] < settings.species_min_similarity
        or species_scores[0] - species_scores[1] < settings.species_min_margin
    ):
        return Decision(
            "uncertain", "This looks like a cat, but the species is not clear enough to identify."
        )
    return Decision(
        "matched",
        "A closest visual match was found. Treat it as a starting point for identification.",
    )
