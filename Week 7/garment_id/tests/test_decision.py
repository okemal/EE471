"""Decision rule and confidence threshold tests."""

import math

import pytest

from backend.app.decision import evaluate_prediction


def test_decision_matched_uncertain_and_low_confidence(config):
    status, _ = evaluate_prediction([0.75, 0.15, 0.10], config)
    assert status == "matched"

    status, _ = evaluate_prediction([0.56, 0.50, 0.0], config)
    assert status == "uncertain"

    status, _ = evaluate_prediction([0.40, 0.30, 0.30], config)
    assert status == "uncertain"

    status, _ = evaluate_prediction([0.15, 0.12, 0.10], config)
    assert status == "no_match"


def test_decision_rejects_empty_and_non_finite(config):
    with pytest.raises(ValueError):
        evaluate_prediction([], config)
    with pytest.raises(ValueError):
        evaluate_prediction([math.nan, 0.5], config)
    with pytest.raises(ValueError):
        evaluate_prediction([math.inf, 0.0], config)
