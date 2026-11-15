"""Deterministic decision thresholds for garment classification confidence."""

import math

from .config import Settings


def evaluate_prediction(probabilities: list[float], config: Settings) -> tuple[str, str]:
    """Classify prediction strength into matched, uncertain, or no_match."""
    if not probabilities or any(not math.isfinite(p) for p in probabilities):
        raise ValueError("Model returned non-finite prediction probabilities.")
    ranked = sorted(probabilities, reverse=True)
    top = ranked[0]
    second = ranked[1] if len(ranked) > 1 else 0.0
    margin = top - second
    if top >= config.confident_min_probability and margin >= config.confident_min_margin:
        return "matched", "Confident garment category match from the optimized CNN."
    if top >= config.uncertain_min_probability:
        return (
            "uncertain",
            "Garment silhouette spans overlapping classes; compare the top candidates "
            "and baseline prediction.",
        )
    return (
        "no_match",
        "Low confidence across all 10 FashionMNIST categories. Try a centered garment "
        "photograph on a plain background.",
    )
