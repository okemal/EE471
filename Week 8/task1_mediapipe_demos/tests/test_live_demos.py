"""Live end-to-end integration tests verifying all 22 MediaPipe 1.2.3 demonstrations."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from run_all import TASK_ORDER


@pytest.mark.live
@pytest.mark.parametrize("task", TASK_ORDER)
def test_live_mediapipe_demo(task: str, tmp_path: Path):
    mod = importlib.import_module(f"demos.{task}")
    result = mod.run_demo(output_path=tmp_path)
    assert result["task"] == task

    if task == "audio_classifier":
        speech_top = result["clips"]["speech"]["windows"][0]["categories"][0]["category"]
        music_top = result["clips"]["music"]["windows"][0]["categories"][0]["category"]
        assert "speech" in speech_top.lower()
        assert "music" in music_top.lower()
    elif task == "audio_transcriber":
        transcript = result["transcript"].lower()
        assert "institute" in transcript and "technology" in transcript
    elif task == "text_to_speech":
        assert Path(result["output_wav"]).is_file()
        assert result["duration_s"] > 1.0
        assert result["stream_chunks"] >= 1
    elif task == "decision_maker":
        routes = [d["selected"] for d in result["decisions"]]
        assert routes == ["technical", "billing", "feature_request"]
    elif task == "semantic_retriever":
        top_ids = [q["hits"][0]["id"] for q in result["queries"]]
        assert top_ids == ["doc_cog", "doc_iztech"]
    elif task == "universal_embedder":
        assert result["similarity_match"] > result["similarity_unrelated"]
    elif task == "language_detector":
        for item in result["predictions"]:
            assert item["predicted"] == item["expected"]
    elif task == "text_classifier":
        labels = [item["categories"][0]["category"] for item in result["predictions"]]
        assert labels == ["positive", "negative", "positive"]
    elif task == "text_embedder":
        assert result["similarity_similar"] > result["similarity_unrelated"]
    elif task == "text_proofreader":
        corrected = result["results"][0]["corrected"]
        assert "There are several typos in this sentence" in corrected
    elif task == "text_summarizer":
        assert len(result["summaries"]["tldr"]) > 20
        assert len(result["summaries"]["keypoints"]) > 20
    elif task == "face_detector":
        assert len(result["faces"]) >= 1
        assert Path(result["output_image"]).is_file()
    elif task == "face_landmarker":
        assert result["num_faces"] == 1
        assert result["num_landmarks"] == 478
        assert result["has_transform_matrix"] is True
        assert Path(result["output_image"]).is_file()
    elif task == "gesture_recognizer":
        gestures = [r["gestures"][0]["gesture"] for r in result["results"]]
        assert gestures == ["Thumb_Up", "Victory"]
    elif task == "hand_landmarker":
        assert len(result["hands"]) == 2
        assert all(h["num_landmarks"] == 21 for h in result["hands"])
    elif task == "holistic_landmarker":
        assert result["counts"]["pose_landmarks"] == 33
        assert result["counts"]["face_landmarks"] == 478
    elif task == "image_classifier":
        top_burger = result["results"][0]["top_categories"][0]["category"].lower()
        assert "burger" in top_burger
    elif task == "image_embedder":
        assert result["similarity_similar"] > result["similarity_different"]
    elif task == "image_segmenter":
        labels = {c["label"] for c in result["classes"]}
        assert "dog" in labels or "cat" in labels
    elif task == "interactive_segmenter":
        assert 0.05 < result["foreground_ratio"] < 0.85
    elif task == "object_detector":
        cats = {d["category"] for d in result["detections"]}
        assert {"cat", "dog"}.issubset(cats)
    elif task == "pose_landmarker":
        assert len(result["results"]) == 3
        assert all(r["num_landmarks"] == 33 for r in result["results"])
