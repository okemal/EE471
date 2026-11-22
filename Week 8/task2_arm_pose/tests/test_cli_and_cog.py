"""CLI and Cog Runner unit tests for Week 8 Task 2."""

from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import classify_arm
from arm_pose.classifier import ArmMetrics, ArmPoseResult


def _import_run_with_stub(monkeypatch):
    if "cog" not in sys.modules:
        cog_mod = types.ModuleType("cog")

        class BaseRunner:
            pass

        def Input(description: str = ""):
            return description

        cog_mod.BaseRunner = BaseRunner
        cog_mod.Input = Input
        cog_mod.Path = Path
        monkeypatch.setitem(sys.modules, "cog", cog_mod)
    if "run" in sys.modules:
        return importlib.reload(sys.modules["run"])
    return importlib.import_module("run")


class _StubClassifier:
    def __init__(self, label: str = "left", *, fail: bool = False) -> None:
        self._label = label
        self._fail = fail

    def load(self) -> None:
        pass

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def predict_path(self, image_path: Path):
        if self._fail:
            raise FileNotFoundError(f"missing {image_path}")
        res = ArmPoseResult(
            label=self._label,
            pose_detected=self._label != "None",
            torso_scale=0.3,
            left=ArmMetrics("left", self._label in ("left", "both"), 0.5, 0.2, 0.99, 0.99),
            right=ArmMetrics("right", self._label in ("right", "both"), -0.2, -0.4, 0.99, 0.99),
        )
        return res, [], np.zeros((32, 32, 3), dtype=np.uint8)


def test_cli_outputs_exact_label_json_and_errors(tmp_path: Path, monkeypatch, capsys):
    img = tmp_path / "sample.jpg"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(img)

    monkeypatch.setattr(classify_arm, "ArmPoseClassifier", lambda cfg: _StubClassifier("left"))
    annotated = tmp_path / "ann.png"
    assert classify_arm.main([str(img), "--annotate", str(annotated)]) == 0
    assert capsys.readouterr().out.strip() == "left"
    assert annotated.is_file()

    assert classify_arm.main([str(img), "--json"]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["label"] == "left"

    monkeypatch.setattr(classify_arm, "ArmPoseClassifier", lambda cfg: _StubClassifier(fail=True))
    assert classify_arm.main([str(tmp_path / "missing.jpg")]) == 1
    assert "error:" in capsys.readouterr().err


def test_cog_runner_setup_predict_and_failure_log(tmp_path: Path, monkeypatch):
    run_mod = _import_run_with_stub(monkeypatch)
    monkeypatch.setattr(run_mod, "ArmPoseClassifier", lambda cfg: _StubClassifier("both"))

    runner = run_mod.Runner()
    runner.setup()

    img = tmp_path / "test.jpg"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(img)
    assert runner.run(image=img) == "both"

    runner.classifier = _StubClassifier(fail=True)
    with pytest.raises(FileNotFoundError):
        runner.run(image=tmp_path / "nope.jpg")

    lines = Path("/tmp/arm-pose-predictions.jsonl").read_text(encoding="utf-8").strip().splitlines()
    events = [json.loads(line)["event"] for line in lines[-3:]]
    assert "prediction" in events
    assert events[-1] == "failed"
