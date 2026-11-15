"""Unit tests for CIFAR-10 prediction confidence decision rules."""

import math

import pytest

from backend.app.decision import evaluate_prediction


def test_evaluate_prediction_branches(config):
    status, msg = evaluate_prediction([0.85, 0.05, 0.10], config)
    assert status == "matched"
    assert "ResNet-9" in msg

    status_margin, _ = evaluate_prediction([0.56, 0.50], config)
    assert status_margin == "uncertain"

    status_uncertain, _ = evaluate_prediction([0.38, 0.25, 0.37], config)
    assert status_uncertain == "uncertain"

    status_low, msg_low = evaluate_prediction([0.18, 0.17, 0.15, 0.50 - 0.3], config)
    assert status_low == "no_match"
    assert "CIFAR-10" in msg_low


def test_evaluate_prediction_rejects_empty_or_nonfinite(config):
    with pytest.raises(ValueError):
        evaluate_prediction([], config)
    with pytest.raises(ValueError):
        evaluate_prediction([math.nan, 0.5], config)
