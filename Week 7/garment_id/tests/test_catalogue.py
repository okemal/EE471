"""Garment catalogue schema and validation tests."""

import json

import pytest

from backend.app import catalogue


def test_catalogue_contains_all_ten_fashionmnist_classes():
    items = catalogue.garment_catalogue()
    assert len(items) == 10
    assert [item["class_index"] for item in items] == list(range(10))
    assert catalogue.get_garment("sneaker")["label"] == "Sneaker"
    assert catalogue.get_garment_by_index(6)["id"] == "shirt"
    assert catalogue.get_garment_by_label("Ankle boot")["class_index"] == 9
    assert catalogue.get_garment("unknown") is None


def test_catalogue_validation_errors(tmp_path, monkeypatch):
    bad_count = tmp_path / "bad_count.json"
    bad_count.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(catalogue, "DATA_PATH", bad_count)
    catalogue.garment_catalogue.cache_clear()
    with pytest.raises(ValueError, match="Expected 10"):
        catalogue.garment_catalogue()

    bad_idx = tmp_path / "bad_idx.json"
    entries = [{"id": f"c{i}", "class_index": i, "label": f"L{i}"} for i in range(10)]
    entries[5]["class_index"] = 99
    bad_idx.write_text(json.dumps(entries), encoding="utf-8")
    monkeypatch.setattr(catalogue, "DATA_PATH", bad_idx)
    catalogue.garment_catalogue.cache_clear()
    with pytest.raises(ValueError, match="Class index mismatch"):
        catalogue.garment_catalogue()

    dup = tmp_path / "dup.json"
    entries = [{"id": "same", "class_index": i, "label": f"L{i}"} for i in range(10)]
    dup.write_text(json.dumps(entries), encoding="utf-8")
    monkeypatch.setattr(catalogue, "DATA_PATH", dup)
    catalogue.garment_catalogue.cache_clear()
    with pytest.raises(ValueError, match="Duplicate"):
        catalogue.garment_catalogue()
    catalogue.garment_catalogue.cache_clear()
