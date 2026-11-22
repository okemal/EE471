"""Offline unit tests for Task 1 model manifest, sample audio/image helpers, and runner."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from mediapipe_demos.models import MODEL_SPECS, ensure_model, sha256_file
from mediapipe_demos.samples import (
    read_wav_float32,
    resample_linear,
    synthesize_music_wav,
    write_wav_pcm16,
)
from mediapipe_demos.visualize import (
    colorize_category_mask,
    draw_detections,
    draw_landmark_points,
    load_rgb_image,
    overlay_binary_mask,
    save_rgb_image,
)
from run_all import TASK_ORDER, run_selected_tasks


def test_model_manifest_covers_all_22_solutions():
    assert len(MODEL_SPECS) == 22
    assert set(TASK_ORDER) == set(MODEL_SPECS.keys())
    domains = {spec.domain for spec in MODEL_SPECS.values()}
    assert domains == {"audio", "decision", "retrieval", "text", "vision"}
    for task, spec in MODEL_SPECS.items():
        assert spec.task == task
        assert spec.url.startswith("https://huggingface.co/litert-community/")
        assert spec.approx_mb > 0


def test_ensure_model_rejects_unknown_and_respects_offline(tmp_path: Path, monkeypatch):
    with pytest.raises(KeyError):
        ensure_model("nonexistent_task", cache_dir=tmp_path)

    with pytest.raises(FileNotFoundError):
        ensure_model("face_detector", model_path=tmp_path / "missing.tflite")

    monkeypatch.setenv("MEDIAPIPE_DEMOS_OFFLINE", "1")
    with pytest.raises(FileNotFoundError, match="Offline mode"):
        ensure_model("face_detector", cache_dir=tmp_path)

    cached = tmp_path / MODEL_SPECS["face_detector"].filename
    cached.write_bytes(b"fake-tflite")
    assert ensure_model("face_detector", cache_dir=tmp_path) == cached
    assert len(sha256_file(cached)) == 64


def test_wav_roundtrip_resample_and_music_synthesis(tmp_path: Path):
    wav_path = tmp_path / "tone.wav"
    t = np.linspace(0.0, 0.25, 6000, endpoint=False, dtype=np.float32)
    samples = 0.5 * np.sin(2.0 * np.pi * 440.0 * t)
    write_wav_pcm16(wav_path, samples, 24000)

    loaded, sr = read_wav_float32(wav_path)
    assert sr == 24000
    assert loaded.shape == samples.shape
    assert np.allclose(loaded, samples, atol=1e-3)

    resampled = resample_linear(loaded, 24000, 16000)
    assert len(resampled) == 4000

    music_path = synthesize_music_wav(tmp_path / "music.wav", sample_rate_hz=16000, duration_s=1.0)
    music_samples, music_sr = read_wav_float32(music_path)
    assert music_sr == 16000
    assert len(music_samples) == 16000
    assert float(np.max(np.abs(music_samples))) > 0.5


def test_visualization_helpers_produce_valid_rgb_images(tmp_path: Path):
    src = tmp_path / "sample.png"
    Image.new("RGBA", (64, 48), (120, 80, 40, 255)).save(src)
    rgb = load_rgb_image(src)
    assert rgb.shape == (48, 64, 3)

    fake_det = SimpleNamespace(
        bounding_box=SimpleNamespace(origin_x=8, origin_y=8, width=24, height=24),
        categories=[SimpleNamespace(category_name="dog", score=0.91)],
        keypoints=[SimpleNamespace(x=0.5, y=0.5)],
    )
    det_img = draw_detections(rgb, [fake_det])
    assert det_img.shape == rgb.shape

    lms = [SimpleNamespace(x=0.2, y=0.3), SimpleNamespace(x=0.7, y=0.6)]
    lm_img = draw_landmark_points(rgb, [lms], connections=[(0, 1)])
    assert lm_img.shape == rgb.shape

    mask = np.zeros((48, 64), dtype=np.int32)
    mask[10:30, 10:40] = 3
    seg_img = colorize_category_mask(rgb, mask)
    assert seg_img.shape == rgb.shape

    bin_img = overlay_binary_mask(rgb, (mask > 0).astype(np.float32), point_norm=(0.4, 0.4))
    assert bin_img.shape == rgb.shape

    out = save_rgb_image(bin_img, tmp_path / "out.png")
    assert out.is_file() and out.stat().st_size > 0


def test_run_selected_tasks_captures_success_and_failure(tmp_path: Path, monkeypatch):
    import importlib

    fake_ok = SimpleNamespace(run_demo=lambda output_path=None: {"ok": True})

    def fake_boom(output_path=None):
        raise RuntimeError("boom")

    fake_fail = SimpleNamespace(run_demo=fake_boom)

    def fake_import(name: str):
        return fake_ok if name == "demos.face_detector" else fake_fail

    import run_all

    monkeypatch.setattr(run_all, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(importlib, "import_module", fake_import)

    report = run_selected_tasks(["face_detector", "object_detector"], output_dir=tmp_path / "out")
    assert report["passed"] == 1
    assert report["failed"] == 1
    assert (tmp_path / "artifacts" / "demo_results.json").is_file()
