"""CLI and Cog Runner unit tests for Week 8 Task 3."""

from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import classify_face
from face_direction.classifier import FaceDirectionResult, NoFaceDetectedError


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
    def __init__(self, direction: str = "straight", *, fail: bool = False) -> None:
        self._direction = direction
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
            raise NoFaceDetectedError(f"No face in {image_path}")
        res = FaceDirectionResult(
            direction=self._direction,
            signal_source="pose_matrix",
            yaw_deg=-32.5 if self._direction == "left" else 0.0,
            pitch_deg=0.5,
            roll_deg=1.0,
            asymmetry=-0.6 if self._direction == "left" else 0.0,
            gaze_score=0.0,
        )
        return res, [], np.zeros((32, 32, 3), dtype=np.uint8)


def test_cli_outputs_exact_label_json_and_errors(tmp_path: Path, monkeypatch, capsys):
    img = tmp_path / "face.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(img)

    monkeypatch.setattr(
        classify_face, "FaceDirectionClassifier", lambda cfg: _StubClassifier("left")
    )
    annotated = tmp_path / "ann.png"
    assert classify_face.main([str(img), "--annotate", str(annotated)]) == 0
    assert capsys.readouterr().out.strip() == "left"
    assert annotated.is_file()

    assert classify_face.main([str(img), "--json"]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["direction"] == "left"

    monkeypatch.setattr(
        classify_face, "FaceDirectionClassifier", lambda cfg: _StubClassifier(fail=True)
    )
    assert classify_face.main([str(img)]) == 1
    assert "error:" in capsys.readouterr().err


def test_cog_runner_setup_predict_and_failure_log(tmp_path: Path, monkeypatch):
    run_mod = _import_run_with_stub(monkeypatch)
    monkeypatch.setattr(run_mod, "FaceDirectionClassifier", lambda cfg: _StubClassifier("right"))

    runner = run_mod.Runner()
    runner.setup()

    img = tmp_path / "face.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(img)
    assert runner.run(image=img) == "right"

    runner.classifier = _StubClassifier(fail=True)
    with pytest.raises(NoFaceDetectedError):
        runner.run(image=img)

    lines = (
        Path("/tmp/face-direction-predictions.jsonl")
        .read_text(encoding="utf-8")
        .strip()
        .splitlines()
    )
    events = [json.loads(line)["event"] for line in lines[-3:]]
    assert "prediction" in events
    assert events[-1] == "failed"
