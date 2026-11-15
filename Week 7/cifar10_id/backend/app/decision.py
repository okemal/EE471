"""Deterministic decision thresholds for CIFAR-10 classification confidence."""

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
        return "matched", "Confident CIFAR-10 category match from the optimized ResNet-9."
    if top >= config.uncertain_min_probability:
        return (
            "uncertain",
            "Subject features overlap nearby CIFAR-10 categories; compare the top candidates "
            "and baseline output.",
        )
    return (
        "no_match",
        "Low confidence across all 10 CIFAR-10 categories. Try a centered photograph of a "
        "single vehicle or animal.",
    )
