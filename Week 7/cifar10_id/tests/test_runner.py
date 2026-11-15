"""Tests for the Cog Runner entry point (run.py)."""

import importlib
import json
import sys
import types
from dataclasses import replace

import pytest
from PIL import Image

from backend.app.cog_transport import encode_image
from backend.app.images import InvalidImage
from tests.test_model import _write_test_checkpoints


def _import_run_with_stub(monkeypatch):
    if "cog" not in sys.modules:
        cog_mod = types.ModuleType("cog")

        class BaseRunner:
            pass

        def Input(description=""):
            return description

        cog_mod.BaseRunner = BaseRunner
        cog_mod.Input = Input
        monkeypatch.setitem(sys.modules, "cog", cog_mod)
    if "run" in sys.modules:
        return importlib.reload(sys.modules["run"])
    return importlib.import_module("run")


def test_runner_setup_predict_and_error_logging(config, monkeypatch):
    run_mod = _import_run_with_stub(monkeypatch)
    active_cfg = replace(config, load_model=True, device="cpu")
    monkeypatch.setattr(run_mod, "settings", active_cfg)

    runner = run_mod.Runner()
    with pytest.raises(RuntimeError):
        runner.setup()

    _write_test_checkpoints(active_cfg.cache_dir, same_winner=False)
    runner.setup()

    img = Image.new("RGB", (32, 32), (30, 80, 140))
    data_uri = encode_image(img)
    output = runner.run(image=data_uri)
    assert output["optimized"]["predicted_id"] == "airplane"
    assert output["baseline"]["predicted_id"] == "ship"
    assert output["comparison"]["agreement"] is False

    with pytest.raises(InvalidImage, match="URLs are not accepted"):
        runner.run(image="http://127.0.0.1/invalid")

    log_lines = open("/tmp/cifar10-predictions.jsonl", encoding="utf-8").read().strip().splitlines()
    parsed = [json.loads(line) for line in log_lines[-3:]]
    assert any(entry["event"] == "prediction" for entry in parsed)
    assert parsed[-1]["event"] == "failed"
