import pytest

from backend.app.decision import decide


@pytest.mark.parametrize(
    "cat,other,species,status",
    [
        (0.34, 0.20, [0.60, 0.45], "matched"),
        (0.21, 0.10, [0.60, 0.45], "no_match"),
        (0.30, 0.35, [0.60, 0.45], "no_match"),
        (0.30, 0.29, [0.60, 0.45], "no_match"),
        (0.34, 0.20, [0.50, 0.495], "uncertain"),
        (0.34, 0.20, [0.19, 0.10], "uncertain"),
        (0.34, 0.20, [], "uncertain"),
    ],
)
def test_abstention_decisions(config, cat, other, species, status):
    assert decide(cat, other, species, config).status == status


def test_cat_and_other_tie_is_not_a_match(config):
    assert decide(0.3, 0.3, [0.6, 0.3], config).status == "no_match"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_invalid_model_output_fails_closed(config, value):
    with pytest.raises(ValueError):
        decide(value, 0.2, [0.6, 0.4], config)
    with pytest.raises(ValueError):
        decide(0.3, 0.2, [value, 0.4], config)
