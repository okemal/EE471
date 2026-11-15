"""Tests for the validated 10-class CIFAR-10 catalogue loader."""

import json

import pytest

from backend.app import catalogue as cat_mod


def test_catalogue_contains_all_ten_cifar10_classes():
    items = cat_mod.cifar_catalogue()
    assert len(items) == 10
    assert [item["label"] for item in items] == [
        "plane",
        "car",
        "bird",
        "cat",
        "deer",
        "dog",
        "frog",
        "horse",
        "ship",
        "truck",
    ]
    assert cat_mod.get_cifar_class("ship")["class_index"] == 8
    assert cat_mod.get_cifar_class("unknown") is None
    assert cat_mod.get_cifar_class_by_index(3)["id"] == "cat"
    assert cat_mod.get_cifar_class_by_label("car")["id"] == "automobile"


def test_catalogue_validation_errors(tmp_path, monkeypatch):
    bad_count = tmp_path / "count.json"
    bad_count.write_text("[]", encoding="utf-8")
    cat_mod.cifar_catalogue.cache_clear()
    monkeypatch.setattr(cat_mod, "DATA_PATH", bad_count)
    with pytest.raises(ValueError, match="Expected 10"):
        cat_mod.cifar_catalogue()

    valid = json.loads(
        (cat_mod.Path(__file__).resolve().parents[1] / "backend/app/data/classes.json").read_text(
            encoding="utf-8"
        )
    )
    bad_idx = list(valid)
    bad_idx[0] = {**bad_idx[0], "class_index": 5}
    p_idx = tmp_path / "idx.json"
    p_idx.write_text(json.dumps(bad_idx), encoding="utf-8")
    cat_mod.cifar_catalogue.cache_clear()
    monkeypatch.setattr(cat_mod, "DATA_PATH", p_idx)
    with pytest.raises(ValueError, match="Class index mismatch"):
        cat_mod.cifar_catalogue()

    dup = list(valid)
    dup[1] = {**dup[1], "id": dup[0]["id"]}
    p_dup = tmp_path / "dup.json"
    p_dup.write_text(json.dumps(dup), encoding="utf-8")
    cat_mod.cifar_catalogue.cache_clear()
    monkeypatch.setattr(cat_mod, "DATA_PATH", p_dup)
    with pytest.raises(ValueError, match="Duplicate"):
        cat_mod.cifar_catalogue()

    cat_mod.cifar_catalogue.cache_clear()
